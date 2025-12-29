import unittest
from unittest.mock import MagicMock, patch
import os
from agents.llm_core import get_llm_provider, AnthropicLLM, OpenAILLM, MockLLM, ACTION_MAPPING

class TestNewProviders(unittest.TestCase):
    
    def test_factory_ollama(self):
        llm = get_llm_provider("ollama")
        self.assertIsInstance(llm, OpenAILLM)
        self.assertEqual(llm.base_url, "http://localhost:11434/v1")
        self.assertEqual(llm.model_name, "llama3.1")

    def test_factory_groq(self):
        llm = get_llm_provider("groq", api_key="g-123")
        self.assertIsInstance(llm, OpenAILLM)
        self.assertEqual(llm.base_url, "https://api.groq.com/openai/v1")
        self.assertEqual(llm.model_name, "llama3-70b-8192")

    def test_factory_anthropic(self):
        # Patch init to avoid needing key
        with patch('agents.llm_core.AnthropicLLM.__init__', return_value=None):
            llm = get_llm_provider("anthropic")
            self.assertIsInstance(llm, AnthropicLLM)

    @patch('anthropic.Anthropic')
    def test_anthropic_generation(self, mock_anthropic_cls):
        # Setup Mock Client
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        
        # Setup Mock Response
        mock_msg = MagicMock()
        mock_msg.stop_reason = "tool_use"
        
        # Mock Content Block
        mock_content = MagicMock()
        mock_content.type = "tool_use"
        mock_content.name = "MoveAction"
        mock_content.input = {"target": "Player"}
        
        mock_msg.content = [mock_content]
        mock_client.messages.create.return_value = mock_msg
        
        llm = AnthropicLLM(api_key="sk-ant-test")
        
        response = llm.generate_response("Sys", "User")
        
        self.assertEqual(response["action"], "MOVE") # Checked against ACTION_MAPPING
        self.assertEqual(response["target"], "Player")
        
        # Verify call structure
        args, kwargs = mock_client.messages.create.call_args
        self.assertEqual(kwargs['model'], "claude-3-5-sonnet-20241022")
        self.assertEqual(len(kwargs['tools']), 31) # Check tool count (31 actions in ALL_ACTIONS)

    def test_action_mapping_integrity(self):
        # Ensure mapping covers key actions
        self.assertEqual(ACTION_MAPPING["AttackAction"], "SET_COMBAT_MODE")
        self.assertEqual(ACTION_MAPPING["MoveAction"], "MOVE")
        self.assertEqual(ACTION_MAPPING["ChatAction"], "CHAT")

if __name__ == '__main__':
    unittest.main()
