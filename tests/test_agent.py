import asyncio
import json
import unittest
from unittest.mock import AsyncMock

from agents.agent import AgentController
from agents.llm_core import MockLLM
from agents.session import ActionResult


class FakeWebSocket:
    def __init__(self):
        self.sent = []
        self.closed = False

    async def __aiter__(self):
        return self

    async def __anext__(self):
        await asyncio.Event().wait()

    async def send(self, message):
        self.sent.append(json.loads(message))

    async def close(self):
        self.closed = True


class TestAgentController(unittest.TestCase):
    def setUp(self):
        self.ws = FakeWebSocket()
        self.ctrl = AgentController(
            bot_id="TestBot",
            mission="Test mission",
            llm=MockLLM(),
            orchestrator_url="ws://localhost:8000/ws",
        )
        self.ctrl.ws = self.ws

    def test_initial_state(self):
        self.assertEqual(self.ctrl.state, "spawning")
        self.assertEqual(self.ctrl.bot_id, "TestBot")
        self.assertEqual(len(self.ctrl.tools), 41)
        self.assertTrue(self.ctrl.tools.has("MOVE"))
        self.assertTrue(self.ctrl.tools.has("RECALL"))
        self.assertFalse(self.ctrl.tools.has("BROADCAST"))

    def test_handle_action_result(self):
        asyncio.run(self._async_test_handle_action_result())

    async def _async_test_handle_action_result(self):
        self.ctrl.session.start_action("cmd_001", "MOVE", {})
        await self.ctrl._handle_action_result({
            "id": "cmd_001",
            "status": "completed",
            "endSignal": "Arrived",
        })
        self.assertFalse(self.ctrl.session.has_pending_action())
        self.assertEqual(self.ctrl.session.current_action.result.status, "completed")

    def test_handle_observation(self):
        asyncio.run(self._async_test_handle_observation())

    async def _async_test_handle_observation(self):
        future = asyncio.get_running_loop().create_future()
        self.ctrl._obs_future = future
        await self.ctrl._handle_observation({"position": {"x": 10, "y": 64, "z": 20}})
        self.assertTrue(future.done())
        self.assertEqual(future.result()["position"]["x"], 10)

    def test_chat_interrupt(self):
        asyncio.run(self._async_test_chat_interrupt())

    async def _async_test_chat_interrupt(self):
        self.assertEqual(self.ctrl.session.interrupt_queue.qsize(), 0)
        await self.ctrl._handle_chat({"username": "PlayerX", "message": "hello"})
        self.assertEqual(self.ctrl.session.interrupt_queue.qsize(), 1)

    def test_event_interrupt(self):
        asyncio.run(self._async_test_event_interrupt())

    async def _async_test_event_interrupt(self):
        await self.ctrl._handle_event({"message": "zombie spotted"})
        self.assertEqual(self.ctrl.session.interrupt_queue.qsize(), 1)

    def test_memorize_action_result(self):
        asyncio.run(self._async_test_memorize())

    async def _async_test_memorize(self):
        self.ctrl.session.start_action("cmd_001", "MOVE", {})
        self.ctrl.session.resolve_action(ActionResult(cmd_id="cmd_001", status="completed", end_signal="Arrived at village"))
        initial_events = len(self.ctrl.memory.episodic.events)
        await self.ctrl._memorize_action_result()
        self.assertEqual(len(self.ctrl.memory.episodic.events), initial_events + 1)
        self.assertIn("Arrived at village", self.ctrl.memory.episodic.events[-1]["event"])

    def test_build_context(self):
        asyncio.run(self._async_test_build_context())

    async def _async_test_build_context(self):
        self.ctrl.memory.add_fact("home", "cobblestone house")
        context = await self.ctrl.build_context({"position": {"x": 0, "y": 64, "z": 0}})
        self.assertGreater(len(context), 0)
        self.assertEqual(context[0]["role"], "system")

    def test_execute_cycle_spawning(self):
        asyncio.run(self._async_test_execute_cycle_spawning())

    async def _async_test_execute_cycle_spawning(self):
        self.assertEqual(self.ctrl.state, "spawning")
        self.ctrl._request_observation = AsyncMock(return_value={})
        await self.ctrl._execute_cycle()
        self.assertEqual(self.ctrl.state, "waiting_for_body")

    def test_send_to_body_no_ws(self):
        asyncio.run(self._async_test_send_no_ws())

    async def _async_test_send_no_ws(self):
        ctrl_no_ws = AgentController(
            bot_id="NoWSTest",
            mission="Test",
            llm=MockLLM(),
            orchestrator_url="ws://localhost:8000/ws",
        )
        result = await ctrl_no_ws._send_to_body({"action": "MOVE"})
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
