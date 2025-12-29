import unittest
from unittest.mock import MagicMock, patch
import json
import os
import shutil
from agents.controller import AgentController
from agents.llm_core import MockLLM

class TestIntegrationMock(unittest.TestCase):
    def setUp(self):
        self.test_dir = "tests/data_int_temp"
        if not os.path.exists(self.test_dir):
            os.makedirs(self.test_dir)
        self.bot_id = "IntegrationBot"
        self.llm = MockLLM()
        self.controller = AgentController("http://mock-url", self.llm, "Integration Mission", self.bot_id, profile_path=None)
        # Override storage path for test
        self.controller.storage.folder = self.test_dir
        self.controller.storage.filepath = os.path.join(self.test_dir, f"{self.bot_id}_memory.json")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    @patch('requests.get')
    @patch('requests.post')
    def test_full_loop_cycle(self, mock_post, mock_get):
        # 1. Setup Mock Observation
        mock_obs = {
            "position": {"x": 100, "y": 64, "z": 100},
            "health": 20,
            "food": 20,
            "inventory": [],
            "nearby_entities": [],
            "nearby_blocks": ["dirt"],
            "chat_history": [{"username": "Steve", "message": "Hello"}],
            "action_state": {"status": "idle"}
        }
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_obs

        # 2. Setup Mock Action Response
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"status": "queued", "action_id": "123"}

        # 3. Run One Cycle
        obs = self.controller.observe()
        self.assertIsNotNone(obs)
        
        # Reason (MockLLM returns random action, we just check it returns something)
        # We need to ensure MockLLM returns a dict. In previous step I updated it to return one of many.
        # Let's force it for this specific test to ensure deterministic assertion if needed, 
        # but the random one is also fine as long as we check keys.
        
        action = self.controller.reason(obs, obs['action_state'])
        self.assertIn('action', action)
        
        # Act
        action_id = self.controller.act(action)
        self.assertEqual(action_id, "123")
        
        # Verify persistence
        self.assertTrue(len(self.controller.memory) > 0)
        self.assertTrue(os.path.exists(self.controller.storage.filepath))

if __name__ == '__main__':
    unittest.main()
