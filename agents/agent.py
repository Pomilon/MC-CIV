import asyncio
import json
import logging
import time
from typing import Literal

import websockets

from agents import config
from agents.context import ContextBuilder
from agents.llm_core import LLMProvider
from agents.memory import MemoryManager
from agents.observation import ObservationRenderer
from agents.session import ActionResult, AgentSession
from agents.tools import ToolRegistry, build_body_tools, build_cognitive_tools

logger = logging.getLogger(__name__)


# Actions that can run concurrently with a pending physical action.
# These are quick, non-conflicting operations (chat, equip, inventory, etc.).
_CONCURRENT_ACTIONS = {"CHAT", "IDLE", "CONFIGURE", "EQUIP", "INVENTORY", "THROW_ITEM", "USE_ITEM"}

# Tools allowed in side conversation (while main physical action runs).
_SIDE_TOOLS = {"CHAT", "IDLE", "EQUIP", "INVENTORY", "THROW_ITEM", "USE_ITEM", "STOP", "CONFIGURE"}


class AgentController:
    def __init__(
        self,
        bot_id: str,
        mission: str,
        llm: LLMProvider,
        orchestrator_url: str,
        profile: dict | None = None,
        token_budget: int = 4096,
    ):
        self.bot_id = bot_id
        self.mission = mission
        self.llm = llm
        self.orchestrator_url = f"{orchestrator_url}/brain/{bot_id}"
        self.profile = profile or {}

        self.ws: websockets.WebSocketClientProtocol | None = None
        self._obs_future: asyncio.Future | None = None

        self.memory = MemoryManager()
        self.session = AgentSession(idle_timeout=config.IDLE_TIMEOUT)
        self.observation_renderer = ObservationRenderer(self.memory)

        async def send_command(cmd: dict) -> str:
            return await self._send_to_body(cmd)

        self.tools = ToolRegistry()
        for tool in build_cognitive_tools(self.memory):
            self.tools.register(tool)
        for tool in build_body_tools(send_command):
            self.tools.register(tool)

        profile_text = f"Name: {self.profile.get('name', bot_id)}\nMission: {mission}" if self.profile else f"Name: {bot_id}\nMission: {mission}"
        self.context_builder = ContextBuilder(
            memory=self.memory,
            system_prompt=self.profile.get("persona", "") if self.profile else "",
            profile=profile_text,
            token_budget=token_budget or config.CONTEXT_TOKEN_BUDGET,
        )

        self.state: Literal["spawning", "thinking", "executing", "waiting_for_body", "side_conversation"] = "spawning"
        self._iteration = 0
        self._body_ready = asyncio.Event()
        self._last_chat_seen: dict[tuple[str, str], float] = {}
        self._side_turns: list[dict] = []

    async def _send_to_body(self, cmd: dict) -> str:
        if not self.ws:
            return json.dumps({"status": "error", "error": "Not connected"})
        try:
            await self.ws.send(json.dumps({"type": "command", "data": cmd}))
            return json.dumps({"status": "sent"})
        except Exception as e:
            logger.error(f"Send failed: {e}")
            return json.dumps({"status": "error", "error": str(e)})

    async def _send_cancel(self, cmd_id: str) -> None:
        if not self.ws:
            return
        try:
            await self.ws.send(json.dumps({"type": "cancel", "data": {"id": cmd_id}}))
        except Exception as e:
            logger.error(f"Cancel send failed: {e}")

    async def run(self):
        logger.info(f"Agent {self.bot_id} connecting to {self.orchestrator_url}")
        while True:
            try:
                async with websockets.connect(self.orchestrator_url, ping_timeout=config.WEBSOCKET_PING_TIMEOUT, ping_interval=config.WEBSOCKET_PING_INTERVAL) as ws:
                    self.ws = ws
                    logger.info(f"Connected as {self.bot_id}")
                    await self._agent_loop()
            except Exception as e:
                logger.error(f"Connection error: {e}, retrying in {config.RECONNECT_DELAY}s")
                await asyncio.sleep(config.RECONNECT_DELAY)

    async def _receive_loop(self):
        async for message in self.ws:
            data = json.loads(message)
            msg_type = data.get("type")
            payload = data.get("data", {})

            try:
                if msg_type == "action_result":
                    await self._handle_action_result(payload)
                elif msg_type == "observation":
                    await self._handle_observation(payload)
                elif msg_type == "chat":
                    await self._handle_chat(payload)
                elif msg_type == "event":
                    await self._handle_event(payload)
                elif msg_type == "spawned":
                    logger.info(f"Bot spawned: {payload}")
                    self._body_ready.set()
                elif msg_type == "connect":
                    logger.info(f"Body connected: {payload}")
                    self._body_ready.set()
                elif msg_type == "error":
                    logger.error(f"Orchestrator error: {payload}")
                    if self._obs_future and not self._obs_future.done():
                        self._obs_future.set_result({})
            except Exception as e:
                logger.error(f"Error handling message {msg_type}: {e}")

    async def _handle_action_result(self, payload: dict) -> None:
        result = ActionResult(
            cmd_id=payload.get("id", ""),
            status=payload.get("status", "completed"),
            end_signal=payload.get("endSignal", ""),
            error=payload.get("error", ""),
            observation=payload.get("observation"),
            raw=payload,
        )
        self.session.resolve_action(result)

    async def _handle_observation(self, payload: dict) -> None:
        if self._obs_future and not self._obs_future.done():
            self._obs_future.set_result(payload)

    async def _handle_chat(self, payload: dict) -> None:
        logger.info(f"[CHAT] {payload.get('username')}: {payload.get('message')}")
        key = (payload.get("username", "?"), payload.get("message", ""))
        now = time.time()
        if key in self._last_chat_seen and now - self._last_chat_seen[key] < 60:
            logger.info(f"Dedup: {key} seen {now - self._last_chat_seen[key]:.0f}s ago")
            return
        self._last_chat_seen[key] = now
        if len(self._last_chat_seen) > 100:
            cutoff = now - 120
            self._last_chat_seen = {k: v for k, v in self._last_chat_seen.items() if v > cutoff}
        self.memory.add_event(
            f"Chat from {payload.get('username')}: {payload.get('message')}",
            importance=config.CHAT_EVENT_IMPORTANCE,
            tags=["chat"],
        )
        self.session.push_interrupt("chat", payload)

    async def _handle_event(self, payload: dict) -> None:
        logger.info(f"[EVENT] {payload.get('message')}")
        self.session.push_interrupt("event", payload)

    async def _request_observation(self) -> dict:
        req_id = f"obs_{int(time.time() * 1000)}"
        self._obs_future = asyncio.get_running_loop().create_future()
        await self.ws.send(json.dumps({"type": "request_observation", "id": req_id}))
        try:
            return await asyncio.wait_for(self._obs_future, timeout=config.OBSERVATION_TIMEOUT)
        except (asyncio.TimeoutError, Exception) as e:
            logger.warning(f"Observation timeout: {e}")
            return {}

    async def _agent_loop(self):
        receiver = asyncio.create_task(self._receive_loop())
        try:
            logger.info("Waiting for body to connect...")
            try:
                await asyncio.wait_for(self._body_ready.wait(), timeout=config.OBSERVATION_TIMEOUT)
            except asyncio.TimeoutError:
                logger.warning("Body did not connect within timeout, continuing anyway")
            await self._execute_cycle()
            while True:
                await self._execute_cycle()
        except asyncio.CancelledError:
            pass
        finally:
            receiver.cancel()

    async def _execute_cycle(self):
        self._iteration += 1

        # --- SPAWNING / SIDE CONVERSATION ---
        try:
            if self.state == "spawning":
                self.state = "thinking"
            elif self.state == "side_conversation":
                await self._execute_side_cycle()
                return
            elif self.state == "waiting_for_body":
                wait_result, interrupt = await self.session.wait_for_action_or_interrupt(timeout=config.IDLE_TIMEOUT)
                if wait_result == "interrupt" and self.session.has_pending_action():
                    await self._fork_side_conversation(interrupt)
                    await self._execute_side_cycle()
                    return
                if wait_result == "done":
                    await self._memorize_action_result()
                self.state = "thinking"
        except Exception as e:
            logger.error(f"Cycle error: {e}", exc_info=True)
            self.state = "waiting_for_body" if self.session.has_pending_action() else "thinking"
            return

        if self.state != "thinking":
            return

        # OBSERVE
        raw_obs = await self._request_observation()
        obs_text = self.observation_renderer.render(raw_obs)

        # Check if there's a pending action (interrupted case)
        extra = f"Your mission: {self.mission}"
        if self.session.has_pending_action():
            pa = self.session.current_action
            extra += (
                f"\n[Note: {pa.action} is still running. "
                f"Player commands override your mission — if a player gave you instructions, follow them immediately. "
                f"Do NOT start a new non-concurrent action until {pa.action} completes. "
                f"Use CHAT to talk or IDLE to wait.]"
            )
        messages = self.context_builder.build(observation=obs_text, extra_context=extra)
        tools = self.tools.declarations()

        try:
            response = self.llm.generate_response(messages, tools=tools)
        except Exception as e:
            logger.error(f"LLM error: {e}")
            await asyncio.sleep(config.LLM_ERROR_BACKOFF)
            self.state = "waiting_for_body" if self.session.has_pending_action() else "thinking"
            return

        action = response.get("action", "IDLE")
        thought = response.get("thought", "")

        logger.info(f"[{self.bot_id}] Thought: {thought}")
        logger.info(f"[{self.bot_id}] Action: {action}")

        # Store model's turn for conversation alternation
        if action == "IDLE":
            self.memory.working.add({"role": "assistant", "content": f"IDLE: {response.get('reason', 'waiting')}"})
        else:
            tc_args = {k: v for k, v in response.items() if k not in ("action", "thought", "tool_call_id")}
            self.memory.working.add({
                "role": "assistant",
                "content": thought,
                "tool_calls": [{"function": {"name": action, "arguments": json.dumps(tc_args)}}],
            })

        # ACT
        if action == "IDLE":
            self.state = "waiting_for_body"
            return

        if self.tools.has(action):
            cmd_id = f"cmd_{int(time.time() * 1000)}"
            tool_obj = self.tools.get(action)
            if tool_obj and tool_obj.category == "cognitive":
                result = await self.tools.execute(action, response)
                logger.info(f"[{self.bot_id}] Cognitive {action}: {result}")
                self.memory.working.add({"role": "tool", "content": f"{action}: {result}", "tool_name": action})
                self.state = "thinking"
            else:
                # Only cancel pending action if the new action is non-concurrent
                if action not in _CONCURRENT_ACTIONS and self.session.has_pending_action():
                    old_id = self.session.current_action.cmd_id
                    logger.info(f"Cancelling pending {self.session.current_action.action}[{old_id}] before {action}")
                    await self._send_cancel(old_id)
                    self.session.cancel_action()
                    self.session.clear_action()
                self.session.start_action(cmd_id, action, response)
                await self._send_to_body({"id": cmd_id, "action": action, **response})
                self.state = "waiting_for_body"
        else:
            logger.warning(f"Unknown action: {action}")
            self.state = "thinking"

    async def _memorize_action_result(self) -> None:
        if not self.session.current_action or not self.session.current_action.done:
            return
        pa = self.session.current_action
        result = getattr(pa, "result", None)
        if result:
            status = result.status
            signal = result.end_signal
            action_str = pa.action
            self.memory.working.add({
                "role": "tool",
                "content": f"Action {action_str}: {status} — {signal}",
                "tool_name": action_str,
            })
            if result.error:
                self.memory.working.add({
                    "role": "tool",
                    "content": f"Error: {result.error}",
                    "tool_name": action_str,
                })
            if status == "completed":
                self.memory.add_event(
                    f"Completed {action_str}: {signal}",
                    importance=config.ACTION_COMPLETED_IMPORTANCE,
                    tags=["action", action_str.lower()],
                )
            elif status == "failed":
                self.memory.add_event(
                    f"Failed {action_str}: {result.error}",
                    importance=config.ACTION_FAILED_IMPORTANCE,
                    tags=["action", "failure"],
                )
            if self._iteration % config.CONSOLIDATE_INTERVAL == 0:
                self.memory.consolidate()
        self.session.clear_action()

    async def _fork_side_conversation(self, wake_interrupt) -> None:
        self.state = "side_conversation"
        if self._side_turns:
            return
        self._side_turns = []
        self._add_interrupts_to_side(self._side_turns, [wake_interrupt] + self.session.drain_interrupts())

    def _add_interrupts_to_side(self, turns: list[dict], interrupts: list) -> None:
        for i in interrupts:
            if i.type == "chat":
                name = i.data.get("username", "Someone")
                msg = i.data.get("message", "")
                if i.received_at:
                    pass
                turns.append({"role": "user", "content": f"{name}: {msg}"})
            elif i.type == "event":
                turns.append({"role": "user", "content": f"[Event: {i.data.get('message', '')}]"})

    async def _execute_side_cycle(self) -> None:
        if not self.session.has_pending_action():
            await self._return_from_side_conversation()
            return
        additional = self.session.drain_interrupts()
        if additional:
            self._add_interrupts_to_side(self._side_turns, additional)
        action_name = self.session.current_action.action if self.session.current_action else "unknown"
        extra = (
            f"Your mission: {self.mission}\n"
            f"[Note: {action_name} is still running. You may only use CHAT, EQUIP items, "
            f"manage inventory, use items, configure, throw items, IDLE, or STOP. "
            f"STOP cancels {action_name} and returns you to full control. "
            f"Always follow player commands immediately.]"
        )
        messages = self.context_builder.build(
            observation=f"[{action_name} is still running. No new observation available.]",
            extra_context=extra,
        )
        for turn in self._side_turns:
            messages.append(turn)
        messages.append({
            "role": "user",
            "content": f"[{action_name} is still running. What do you do?]"
        })
        side_tools = [t for t in self.tools.declarations() if t.__name__ in _SIDE_TOOLS]
        try:
            response = self.llm.generate_response(messages, tools=side_tools)
        except Exception as e:
            logger.error(f"Side LLM error: {e}")
            await asyncio.sleep(config.LLM_ERROR_BACKOFF)
            return
        action = response.get("action", "IDLE")
        thought = response.get("thought", "")
        logger.info(f"[{self.bot_id}] Side: {thought}")
        logger.info(f"[{self.bot_id}] Side action: {action}")
        tc_args = {k: v for k, v in response.items() if k not in ("action", "thought", "tool_call_id")}
        if action == "IDLE":
            self._side_turns.append({
                "role": "assistant",
                "content": f"IDLE: {response.get('reason', 'waiting')}",
            })
        else:
            self._side_turns.append({
                "role": "assistant",
                "content": thought,
                "tool_calls": [{"function": {"name": action, "arguments": json.dumps(tc_args)}}],
            })
        if action == "STOP":
            if self.session.has_pending_action():
                old_id = self.session.current_action.cmd_id
                await self._send_cancel(old_id)
                self.session.cancel_action()
                self.session.clear_action()
            await self._return_from_side_conversation()
            return
        if action == "IDLE":
            pass
        elif action in _CONCURRENT_ACTIONS:
            tool_obj = self.tools.get(action)
            if tool_obj and tool_obj.category == "cognitive":
                result = await self.tools.execute(action, response)
                self._side_turns.append({
                    "role": "tool",
                    "content": f"{action}: {result}",
                    "tool_name": action,
                })
            else:
                cmd_id = f"side_{int(time.time() * 1000)}"
                await self._send_to_body({"id": cmd_id, "action": action, **response})
                self._side_turns.append({
                    "role": "tool",
                    "content": f"Sent {action} command",
                    "tool_name": action,
                })
        elif action != "IDLE":
            logger.warning(f"Invalid side action: {action}")

    async def _return_from_side_conversation(self) -> None:
        summary = self._squash_side_conversation()
        if summary:
            self.memory.working.add({"role": "user", "content": summary})
        self._side_turns = []
        if self.session.current_action and self.session.current_action.done:
            await self._memorize_action_result()
        self.state = "thinking"

    def _squash_side_conversation(self) -> str:
        if not self._side_turns:
            return ""
        lines = ["[Side conversation while acting]"]
        for turn in self._side_turns:
            role = turn.get("role", "")
            content = turn.get("content", "")
            truncated = content[:200]
            if role == "user":
                lines.append(f"  <- {truncated}")
            elif role == "assistant":
                lines.append(f"  -> {truncated}")
            elif role == "tool":
                lines.append(f"  [{truncated}]")
        return "\n".join(lines)

    async def build_context(self, raw_obs: dict) -> list[dict]:
        obs_text = self.observation_renderer.render(raw_obs)
        extra = f"Your mission: {self.mission}"
        return self.context_builder.build(observation=obs_text, extra_context=extra)
