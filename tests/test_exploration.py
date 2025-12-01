import unittest
from agents.grammar import SaveLocation, SetExplorationMode, MoveAction

class TestExplorationGrammar(unittest.TestCase):
    def test_exploration_actions(self):
        # Save Location
        save = SaveLocation(name="Home Base")
        self.assertEqual(save.action, "SAVE_LOCATION")
        self.assertEqual(save.name, "Home Base")

        # Exploration Mode
        explore = SetExplorationMode(mode="wander")
        self.assertEqual(explore.action, "SET_EXPLORATION_MODE")
        self.assertEqual(explore.mode, "wander")
        
        follow = SetExplorationMode(mode="follow", target="Player1")
        self.assertEqual(follow.mode, "follow")
        self.assertEqual(follow.target, "Player1")

if __name__ == '__main__':
    unittest.main()
