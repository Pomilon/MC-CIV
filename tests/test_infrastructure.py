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
        time = self.api.get_time()
        self.assertTrue(isinstance(time, int) or str(time).isdigit())

if __name__ == '__main__':
    unittest.main()
