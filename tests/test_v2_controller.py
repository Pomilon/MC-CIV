import unittest
from unittest.mock import MagicMock, patch
import json
from agents.controller import AgentController
from agents.llm_core import LLMProvider

class MockLLM(LLMProvider):
    def __init__(self):
        self.next_response = {}
    
    def generate_response(self, system_prompt, user_prompt):
        return self.next_response

class TestV2Controller(unittest.TestCase):
    def setUp(self):
        self.mock_llm = MockLLM()
        # Patch requests and storage to avoid side effects
        self.patcher_req = patch('agents.controller.requests')
        self.mock_req = self.patcher_req.start()
        
        self.patcher_storage = patch('agents.controller.StorageManager')
        self.mock_storage_cls = self.patcher_storage.start()
        self.mock_storage = self.mock_storage_cls.return_value
        self.mock_storage.load.return_value = ([], {}) # Memory, Locations
        
        self.controller = AgentController("http://mock:3000", self.mock_llm, "Test Mission")

    def tearDown(self):
        self.patcher_req.stop()
        self.patcher_storage.stop()

    def test_reason_inspect_zone_formatting(self):
        """Test that reason() correctly formats the 3D zone data from observation."""
        
        # Mock Observation with Zone Data
        zone_data = {
            "origin": {"x": 100, "y": 64, "z": 100},
            "size": {"x": 2, "y": 2, "z": 1},
            "layers": [
                [ ["dirt", "stone"] ],  # Y=0 (64)
                [ ["air", "torch"] ]    # Y=1 (65)
            ]
        }
        
        obs = {
            "action_state": {
                "status": "completed",
                "endSignal": "ZoneInspected",
                "data": zone_data
            },
            "chat_history": []
        }
        
        # We need to capture the prompt passed to LLM
        self.mock_llm.generate_response = MagicMock(return_value={"action": "IDLE", "reason": "Waiting"})
        
        self.controller.reason(obs, obs['action_state'])
        
        # Verify the prompt contains the formatted grid
        call_args = self.mock_llm.generate_response.call_args
        system_prompt = call_args[0][0]
        
        self.assertIn("ZONE INSPECTION (Origin: 100, 64, 100):", system_prompt)
        self.assertIn("--- Layer Y+0 (Abs 64) ---", system_prompt)
        self.assertIn("Z+0: [dirt, stone]", system_prompt)
        self.assertIn("--- Layer Y+1 (Abs 65) ---", system_prompt)
        self.assertIn("Z+0: [air, torch]", system_prompt)

    def test_act_sends_correct_payload(self):
        """Test that act() sends the correct JSON payload to the bot."""
        action = {"action": "PLACE_BLOCK", "block_name": "dirt", "position": "100 64 100"}
        
        # Mock successful POST
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "started", "action_id": "123"}
        self.mock_req.post.return_value = mock_response
        
        action_id = self.controller.act(action)
        
        self.assertEqual(action_id, "123")
        self.mock_req.post.assert_called_with(
            "http://mock:3000/act",
            json=action,
            timeout=5
        )

if __name__ == '__main__':
    unittest.main()
