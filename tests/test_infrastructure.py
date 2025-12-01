import unittest
from infrastructure.rcon_client import MockRconClient
from infrastructure.game_state import GameStateAPI

class TestGameStateAPI(unittest.TestCase):
    def setUp(self):
        self.rcon = MockRconClient("localhost", 25575, "password")
        self.api = GameStateAPI(self.rcon)

    def test_get_online_players(self):
        # Mock returns "There are 0 of a max of 20 players online: "
        players = self.api.get_online_players()
        self.assertEqual(players, [])

    def test_get_time(self):
        # Mock returns "The time is 1000"
        time = self.api.get_time()
        self.assertEqual(time, 1000)

if __name__ == '__main__':
    unittest.main()
