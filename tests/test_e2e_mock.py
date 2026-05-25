import asyncio
import json
import os
import subprocess
import sys
import time
import unittest


class TestEndToEndMock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._mock_env = {**os.environ, "MOCK_MODE": "true"}
        cls.orchestrator_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "orchestrator.bus:app",
             "--host", "0.0.0.0", "--port", "8001",
             "--log-level", "warning"],
            env=cls._mock_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(3)

    @classmethod
    def tearDownClass(cls):
        if cls.orchestrator_proc:
            cls.orchestrator_proc.terminate()
            cls.orchestrator_proc.wait(timeout=5)

    def test_agent_process_launches(self):
        proc = subprocess.Popen(
            [sys.executable, "-m", "agents.agent_process",
             "--bot-id", "E2EBot",
             "--mission", "E2E test mission",
             "--provider", "mock",
             "--orchestrator", "ws://localhost:8001/ws",
             "--mode", "mock"],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            env={**self._mock_env, "PYTHONPATH": "."},
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        output = b""
        deadline = time.time() + 15
        found_brain = False
        found_body = False
        while time.time() < deadline:
            try:
                chunk = proc.stdout.read1(4096)
                output += chunk
                text = output.decode("utf-8", errors="replace")
                if "Connecting to" in text:
                    found_brain = True
                if "Connected to Controller" in text:
                    found_body = True
                if found_brain and found_body:
                    break
            except (OSError, ValueError):
                break
            time.sleep(0.1)
        proc.terminate()
        proc.wait(timeout=5)
        output_text = output.decode("utf-8", errors="replace")
        self.assertTrue(
            found_brain,
            f"Brain should have connected.\nOutput:\n{output_text}",
        )
        self.assertTrue(
            found_body,
            f"Body should have connected.\nOutput:\n{output_text}",
        )


class TestComponentIntegration(unittest.TestCase):
    def test_memory_manager(self):
        from agents.memory import MemoryManager

        mm = MemoryManager()
        mm.add_event("test event", importance=2.0, tags=["test"])
        self.assertEqual(len(mm.episodic.events), 1)
        mm.add_fact("key", "value")
        results = mm.semantic.retrieve("key")
        self.assertGreaterEqual(len(results), 1)

    def test_tool_registry(self):
        from agents.tools import ToolRegistry

        tr = ToolRegistry()
        self.assertEqual(len(tr), 0)
        decls = tr.declarations()
        self.assertEqual(len(decls), 0)

    def test_body_tools_built(self):
        from agents.tools import build_body_tools

        async def fake_send(cmd):
            return '{"status": "sent"}'

        tools = build_body_tools(fake_send)
        names = {t.name for t in tools}
        self.assertIn("MOVE", names)
        self.assertIn("CHAT", names)
        self.assertIn("GATHER", names)
        self.assertGreater(len(tools), 20, "Should have 20+ body tools")

    def test_cognitive_tools_built(self):
        from agents.memory import MemoryManager
        from agents.tools import build_cognitive_tools

        mm = MemoryManager()
        tools = build_cognitive_tools(mm)
        names = {t.name for t in tools}
        self.assertIn("RECALL", names)
        self.assertIn("REMEMBER", names)
        self.assertIn("FORGET", names)
        self.assertGreaterEqual(len(tools), 6, "Should have 6 cognitive tools")

    def test_context_builder_with_memory(self):
        from agents.context import ContextBuilder
        from agents.memory import MemoryManager

        mm = MemoryManager()
        mm.add_fact("home", "coordinates (100, 64, -50)")
        mm.add_event("Built a house", importance=3.0)

        cb = ContextBuilder(mm, system_prompt="You are a test agent", profile="TestBot")
        ctx = cb.build(observation="Test observation")
        self.assertGreater(len(ctx), 0)
        content = "\n".join(m.get("content", "") for m in ctx)
        self.assertIn("TestBot", content)
        self.assertIn("Built a house", content)
        self.assertIn("Test observation", content)

    def test_observation_renderer(self):
        from agents.memory import MemoryManager
        from agents.observation import ObservationRenderer

        mm = MemoryManager()
        renderer = ObservationRenderer(mm)

        obs = {
            "position": {"x": 10, "y": 64, "z": 20},
            "biome": "forest",
            "time": 6000,
            "health": 18,
            "food": 14,
            "inventory": [{"name": "diamond_sword", "count": 1}],
            "nearby_entities": [{"name": "zombie", "distance": 5, "hostile": True}],
            "nearby_blocks": ["oak_log", "stone"],
            "chat_history": [{"username": "Player1", "message": "hello"}],
        }
        text = renderer.render(obs)
        self.assertIn("forest", text)
        self.assertIn("zombie", text)
        self.assertIn("Player1", text)
        self.assertIn("diamond_sword", text)

    def test_session_state_machine(self):
        from agents.session import AgentSession, ActionResult

        session = AgentSession(idle_timeout=30.0)
        self.assertFalse(session.has_pending_action())

        session.start_action("cmd_1", "MOVE", {"target": "100 64 100"})
        self.assertTrue(session.has_pending_action())

        session.resolve_action(ActionResult(cmd_id="cmd_1", status="completed", end_signal="Arrived"))
        self.assertFalse(session.has_pending_action())

    def test_interrupt_queue(self):
        from agents.session import AgentSession

        session = AgentSession()
        session.push_interrupt("chat", {"username": "P", "message": "hi"})
        self.assertEqual(session.interrupt_queue.qsize(), 1)

        async def check():
            result, interrupt = await session.wait_for_action_or_interrupt(timeout=1.0)
            self.assertEqual(result, "interrupt")
            self.assertEqual(interrupt.type, "chat")

        asyncio.run(check())

    def test_mock_llm_responds(self):
        from agents.llm_core import MockLLM

        llm = MockLLM()
        result = llm.generate_response([{"role": "user", "content": "do something"}])
        self.assertIn("action", result)
        self.assertIn(result["action"], ["CHAT", "MOVE", "IDLE"])


if __name__ == "__main__":
    unittest.main()
