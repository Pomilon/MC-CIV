import unittest
from unittest.mock import MagicMock, patch
import os
import shutil
import json
import requests
from collections import deque
from tenacity import RetryError

# Import classes to test
from agents.grammar import *
from agents.llm_core import GeminiLLM, OpenAILLM, MockLLM, get_llm_provider
from agents.controller import AgentController
from agents.storage import StorageManager
from narrator.story_engine import StoryEngine
from infrastructure.rcon_client import MockRconClient
from infrastructure.game_state import GameStateAPI

class TestGrammarRobustness(unittest.TestCase):
    def test_all_actions(self):
        # Verify every model accepts valid inputs
        actions = [
            MoveAction(target="Zombie"),
            ChatAction(message="Hi"),
            MineAction(block_name="stone"),
            CraftAction(item_name="stick"),
            EquipAction(item_name="sword"),
            IdleAction(reason="waiting"),
            SetCombatMode(mode="pvp", target="Player"),
            SetSurvivalPreset(preset="brave"),
            BuildStructure(structure_type="wall", location="0 0 0"),
            ManageInventory(task="sort"),
            SaveLocation(name="Home"),
            SetExplorationMode(mode="wander")
        ]
        for a in actions:
            self.assertIsNotNone(a.model_dump())

    def test_invalid_grammar(self):
        # Validate validation logic (pydantic throws)
        with self.assertRaises(ValueError):
            SetCombatMode(mode="invalid_mode") 

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
        
        # Verify file exists
        self.assertTrue(os.path.exists(storage.filepath))
        
        # Load back
        mem_loaded, loc_loaded = storage.load()
        self.assertEqual(list(mem_loaded), list(memory))
        self.assertEqual(loc_loaded, locations)

class TestAgentRobustness(unittest.TestCase):
    @patch('requests.get')
    def test_retry_observe(self, mock_get):
        # Simulate failure then success (Exception must be RequestsException for tenacity to catch it based on my impl)
        # Actually my impl uses retry_if_exception_type(requests.RequestException)
        
        mock_get.side_effect = [requests.exceptions.ConnectionError("Net Error"), requests.exceptions.ConnectionError("Net Error"), MagicMock(status_code=200, json=lambda: {})]
        
        llm = MockLLM()
        controller = AgentController("http://local", llm, "Mission")
        
        # Should succeed eventually
        obs = controller.observe()
        self.assertIsNotNone(obs)
        self.assertEqual(mock_get.call_count, 3)

    @patch('requests.post')
    def test_act_error_handling(self, mock_post):
        mock_post.side_effect = Exception("Fatal Net Error")
        llm = MockLLM()
        controller = AgentController("http://local", llm, "Mission")
        
        # Act should catch exception and update status
        controller.act({"action": "CHAT", "message": "Hi"})
        self.assertEqual(controller.last_action_status, "network_exception")

class TestLLMParsing(unittest.TestCase):
    def test_gemini_fallback(self):
        # We can't easily mock the internal Gemini API call structure without deep mocking
        # But we can test the fallback logic if we mock the `genai.GenerativeModel`
        with patch('google.generativeai.GenerativeModel') as MockModel:
            mock_chat = MockModel.return_value.start_chat.return_value
            # Case: Empty response parts (no function call)
            mock_chat.sendMessage.return_value.parts = []
            
            llm = GeminiLLM(api_key="key")
            res = llm.generate_response("Sys", "User")
            self.assertEqual(res['action'], 'IDLE')
            self.assertIn("No tool called", res['reason'])

class TestStoryEngine(unittest.TestCase):
    def test_narrator_loop(self):
        rcon = MockRconClient("h", 1, "p")
        api = GameStateAPI(rcon)
        llm = MockLLM()
        engine = StoryEngine(api, llm)
        
        # Dry run check state
        engine.check_global_state()

if __name__ == '__main__':
    unittest.main()
