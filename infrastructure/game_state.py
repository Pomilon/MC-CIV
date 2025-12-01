from infrastructure.rcon_client import RconClient, MockRconClient
import re

class GameStateAPI:
    def __init__(self, rcon_client):
        self.rcon = rcon_client

    def get_online_players(self):
        response = self.rcon.send_command("list")
        # Parse: "There are X of a max of Y players online: P1, P2"
        match = re.search(r"online: (.*)", response)
        if match:
            players = match.group(1).split(", ")
            return [p for p in players if p] # Filter empty strings
        return []

    def get_time(self):
        response = self.rcon.send_command("time query daytime")
        # Parse: "The time is X"
        match = re.search(r"is (\d+)", response)
        if match:
            return int(match.group(1))
        return 0

    def broadcast_message(self, message: str):
        # Sanitize message to avoid injection or issues
        safe_message = message.replace('"', '\\"')
        self.rcon.send_command(f'tellraw @a {{"text":"[Narrator] {safe_message}","color":"gold"}}')

    def spawn_entity(self, entity_type, x, y, z):
        self.rcon.send_command(f"summon {entity_type} {x} {y} {z}")

    def set_weather(self, weather_type):
        self.rcon.send_command(f"weather {weather_type}")
