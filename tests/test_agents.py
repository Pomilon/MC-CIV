import unittest

from agents.grammar import CHAT, MOVE
from agents.llm_core import MockLLM


class TestAgents(unittest.TestCase):
    def test_grammar_validation(self):
        move = MOVE(target="player1")
        self.assertEqual(move.action, "MOVE")
        self.assertEqual(move.target, "player1")

        chat = CHAT(message="Hello")
        self.assertEqual(chat.action, "CHAT")
        self.assertEqual(chat.message, "Hello")

    def test_mock_llm(self):
        llm = MockLLM()
        response = llm.generate_response("You are a bot", "Say hello")
        self.assertIn("action", response)


if __name__ == '__main__':
    unittest.main()
