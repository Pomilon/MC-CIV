import asyncio
import logging

from agents import config
from agents.context import ContextBuilder
from agents.grammar import BROADCAST, SPAWN, WAIT, WEATHER
from agents.llm_core import LLMProvider
from agents.memory import MemoryManager
from agents.observation import ObservationRenderer
from agents.tools import ToolRegistry
from agents.tools.registry import Tool

logger = logging.getLogger(__name__)


_NARRATOR_TOOLS: dict[str, tuple[type, str]] = {
    "BROADCAST": (BROADCAST, "Send a message visible to all players on the server."),
    "SPAWN": (SPAWN, "Spawn an entity at a location on the server."),
    "WEATHER": (WEATHER, "Change the weather on the server (clear, rain, thunder)."),
    "WAIT": (WAIT, "Wait without performing any action."),
}


class NarratorAgent:
    def __init__(
        self,
        game_state_api,
        llm: LLMProvider,
        interval: int = config.NARRATOR_INTERVAL,
        token_budget: int = config.NARRATOR_TOKEN_BUDGET,
    ):
        self.api = game_state_api
        self.llm = llm
        self.interval = interval

        self.memory = MemoryManager()
        self.observation_renderer = ObservationRenderer(self.memory)

        self.tools = ToolRegistry()
        for name, (schema, desc) in _NARRATOR_TOOLS.items():
            cls = schema
            tool = Tool(
                name=name,
                description=desc,
                schema=cls,
                handler=self._make_handler(name),
                category="body" if name != "WAIT" else "cognitive",
                requires_body=name != "WAIT",
            )
            self.tools.register(tool)

        self.context_builder = ContextBuilder(
            memory=self.memory,
            system_prompt=(
                "You are the AI Narrator for a Minecraft server. "
                "You drive the story forward with broadcasts, events, and weather changes."
            ),
            profile="Role: Narrator\nYou orchestrate the server's story.",
            token_budget=token_budget,
        )

    def _make_handler(self, action: str):
        async def handler(**kwargs) -> str:
            try:
                if action == "BROADCAST":
                    self.api.broadcast_message(kwargs.get("message", ""))
                    return f"Broadcast: {kwargs.get('message')}"
                elif action == "SPAWN":
                    loc = kwargs.get("location", "random")
                    if loc == "random":
                        self.api.spawn_entity(kwargs["entity_type"], 0, 70, 0)
                    else:
                        parts = loc.split()
                        x, y, z = int(parts[0]), int(parts[1]), int(parts[2])
                        self.api.spawn_entity(kwargs["entity_type"], x, y, z)
                    return f"Spawned {kwargs['entity_type']}"
                elif action == "WEATHER":
                    self.api.set_weather(kwargs.get("type", "clear"))
                    return f"Weather set to {kwargs.get('type')}"
                elif action == "WAIT":
                    return f"Waiting: {kwargs.get('reason', 'no reason')}"
                return f"Unknown action: {action}"
            except Exception as e:
                logger.error(f"Narrator {action} failed: {e}")
                return f"Error: {e}"
        return handler

    async def run_loop(self):
        logger.info("Narrator agent started")
        while True:
            await asyncio.sleep(self.interval)
            try:
                await self._tick()
            except Exception as e:
                logger.error(f"Narrator tick error: {e}")

    async def _tick(self):
        players = self.api.get_online_players()
        if not players:
            return

        day_time = self.api.get_time()
        raw_obs = {
            "time": day_time,
            "biome": "overworld",
            "players": players,
            "chat": [],
        }

        obs_text = self.observation_renderer.render(raw_obs)
        messages = self.context_builder.build(observation=obs_text)
        tools = self.tools.declarations()

        response = self.llm.generate_response(messages, tools=tools)
        action = response.get("action", "WAIT")

        logger.info(f"Narrator: {response.get('thought', '')}")
        logger.info(f"Narrator action: {action}")

        if action == "WAIT":
            return

        if self.tools.has(action):
            await self.tools.execute(action, response)
            self.memory.add_event(
                f"Narrator {action}: {response}",
                importance=config.NARRATOR_EVENT_IMPORTANCE,
                tags=["narrator"],
            )
