import unittest
import os
from unittest.mock import MagicMock, patch
from agents.llm_core import GeminiLLM, OpenAILLM, MockLLM, get_llm_provider

class TestLLMIntegration(unittest.TestCase):
    
    @patch('google.genai.Client')
    def test_gemini_tool_generation(self, mock_client_cls):
        # We test that the tools are generated without error
        llm = GeminiLLM(api_key="fake_key")
        # In my refactor I renamed self.tools to self.default_tools, but exposed self.tools for testing
        self.assertIsNotNone(llm.default_tools)
        # Check if Tool and FunctionDeclarations are present
        self.assertIsInstance(llm.default_tools, list)
        self.assertTrue(len(llm.default_tools) > 0)
        self.assertTrue(hasattr(llm.default_tools[0], 'function_declarations'))
        self.assertEqual(len(llm.default_tools[0].function_declarations), 31) 

    def test_factory(self):
        llm = get_llm_provider("gemini", api_key="test")
        self.assertIsInstance(llm, GeminiLLM)
        
        llm = get_llm_provider("openai", api_key="test")
        self.assertIsInstance(llm, OpenAILLM)
        
        llm = get_llm_provider("unknown")
        self.assertIsInstance(llm, MockLLM) 

if __name__ == '__main__':
    unittest.main()
