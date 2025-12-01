import os
from mcrcon import MCRcon
from tenacity import retry, stop_after_attempt, wait_fixed
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RconClient:
    def __init__(self, host, port, password):
        self.host = host
        self.port = int(port)
        self.password = password
        self.client = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def connect(self):
        try:
            self.client = MCRcon(self.host, self.password, port=self.port)
            self.client.connect()
            logger.info(f"Connected to RCON at {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to RCON: {e}")
            raise

    def disconnect(self):
        if self.client:
            self.client.disconnect()
            logger.info("Disconnected from RCON")

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    def send_command(self, command: str) -> str:
        if not self.client:
            self.connect()
        try:
            response = self.client.command(command)
            return response
        except Exception as e:
            logger.error(f"RCON command failed: {e}")
            # Try reconnecting once
            self.disconnect()
            self.connect()
            return self.client.command(command)

# Mock Client for testing when no server is available
class MockRconClient:
    def __init__(self, host, port, password):
        self.host = host
        self.port = port
        logger.info("Initialized MockRconClient")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def send_command(self, command: str) -> str:
        logger.info(f"Mock RCON Command: {command}")
        if "list" in command:
            return "There are 0 of a max of 20 players online: "
        elif "time" in command:
            return "The time is 1000"
        return "Command executed"
