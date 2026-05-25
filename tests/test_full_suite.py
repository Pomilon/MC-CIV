import os
import shutil
import unittest
from collections import deque
from unittest.mock import MagicMock, patch

from agents.grammar import *
from agents.llm_core import GeminiLLM, MockLLM
from agents.storage import StorageManager
from infrastructure.game_state import GameStateAPI
from infrastructure.rcon_client import MockRconClient
from narrator.agent import NarratorAgent


class TestGrammarRobustness(unittest.TestCase):
    def test_all_actions(self):
        actions = [
            MOVE(target="Zombie"),
            CHAT(message="Hi"),
            MINE(block_name="stone"),
            CRAFT(item_name="stick"),
            EQUIP(item_name="sword"),
            IDLE(reason="waiting"),
            SET_COMBAT_MODE(mode="pvp", target="Player"),
            CONFIGURE(mode="self_defense", setting="fight"),
            BUILD(shape="wall", material="stone", dimensions="10 5 1", location="0 0 0"),
            INVENTORY(task="sort"),
            SAVE_LOCATION(name="Home"),
            SET_EXPLORATION_MODE(mode="wander")
        ]
        for a in actions:
            self.assertIsNotNone(a.model_dump())

    def test_invalid_grammar(self):
        with self.assertRaises(ValueError):
            SET_COMBAT_MODE(mode="invalid_mode")


class TestPersistence(unittest.TestCase):
    def setUp(self):
        self.test_dir = "tests/data_temp"
        if not os.path.exists(self.test_dir):
            os.makedirs(self.test_dir)
        self.bot_id = "TestBotPersistence"

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_save_load(self):
        storage = StorageManager(self.bot_id, self.test_dir)
        memory = deque(["Mem1", "Mem2"], maxlen=15)
        locations = {"Home": "1 2 3"}

        storage.save(memory, locations)
        self.assertTrue(os.path.exists(storage.filepath))

        mem_loaded, loc_loaded, ltm_loaded = storage.load()
        self.assertEqual(list(mem_loaded), list(memory))
        self.assertEqual(loc_loaded, locations)


class TestLLMParsing(unittest.TestCase):
    def test_gemini_fallback(self):
        with patch('google.genai.Client') as mock_client:
            mock_client_inst = mock_client.return_value
            mock_response = MagicMock()
            mock_response.candidates = [MagicMock(content=MagicMock(parts=[]))]
            mock_client_inst.models.generate_content.return_value = mock_response

            llm = GeminiLLM(api_key="key")
            res = llm.generate_response([{"role": "user", "content": "Sys"}])
            self.assertEqual(res['action'], 'IDLE')
            self.assertIn("No tool called", res['reason'])


class TestNarratorAgent(unittest.TestCase):
    def test_narrator_tick(self):
        rcon = MockRconClient("h", 1, "p")
        api = GameStateAPI(rcon)
        llm = MockLLM()
        import asyncio
        agent = NarratorAgent(api, llm, interval=999)
        asyncio.run(agent._tick())


if __name__ == '__main__':
    unittest.main()
