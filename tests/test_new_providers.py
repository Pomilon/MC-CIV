import unittest
from unittest.mock import MagicMock, patch

from agents.llm_core import AnthropicLLM, OpenAILLM, get_llm_provider


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
        with patch('agents.llm_core.AnthropicLLM.__init__', return_value=None):
            llm = get_llm_provider("anthropic")
            self.assertIsInstance(llm, AnthropicLLM)

    @patch('anthropic.Anthropic')
    def test_anthropic_generation(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        mock_msg = MagicMock()
        mock_msg.stop_reason = "tool_use"

        mock_content = MagicMock()
        mock_content.type = "tool_use"
        mock_content.name = "MOVE"
        mock_content.input = {"target": "Player"}

        mock_msg.content = [mock_content]
        mock_client.messages.create.return_value = mock_msg

        llm = AnthropicLLM(api_key="sk-ant-test")

        response = llm.generate_response([{"role": "user", "content": "Sys"}])

        self.assertEqual(response["action"], "MOVE")
        self.assertEqual(response["target"], "Player")

        args, kwargs = mock_client.messages.create.call_args
        self.assertEqual(kwargs['model'], "claude-3-5-sonnet-20241022")
        self.assertEqual(len(kwargs['tools']), 31)


if __name__ == '__main__':
    unittest.main()
