import unittest
from agents.grammar import MoveAction, ChatAction
from agents.llm_core import MockLLM

class TestAgents(unittest.TestCase):
    def test_grammar_validation(self):
        # Valid Move
        move = MoveAction(target="player1")
        self.assertEqual(move.action, "MOVE")
        self.assertEqual(move.target, "player1")

        # Valid Chat
        chat = ChatAction(message="Hello")
        self.assertEqual(chat.action, "CHAT")
        self.assertEqual(chat.message, "Hello")

    def test_mock_llm(self):
        llm = MockLLM()
        response = llm.generate_response("You are a bot", "Say hello")
        self.assertEqual(response["action"], "CHAT")
        self.assertEqual(response["message"], "Mock Response")

if __name__ == '__main__':
    unittest.main()
