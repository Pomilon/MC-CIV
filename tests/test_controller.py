import unittest
from unittest.mock import MagicMock, patch
from agents.controller import AgentController
from agents.llm_core import MockLLM

class TestAgentController(unittest.TestCase):
    @patch('requests.get')
    @patch('requests.post')
    def test_loop_step(self, mock_post, mock_get):
        # Mock Observation
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "name": "Bot1",
            "health": 20,
            "position": {"x": 100, "y": 64, "z": 100}
        }

        llm = MockLLM()
        controller = AgentController("http://localhost:3000", llm, "Survive")
        
        # Run one step manually
        obs = controller.observe()
        self.assertIsNotNone(obs)
        
        action = controller.reason(obs, action_state={})
        self.assertIn("action", action)
        
        controller.act(action)
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs['json']['action'], action['action'])

if __name__ == '__main__':
    unittest.main()
