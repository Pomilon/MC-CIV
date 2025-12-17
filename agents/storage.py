import json
import os
import logging
from collections import deque

logger = logging.getLogger(__name__)

class StorageManager:
    def __init__(self, bot_id: str, data_dir: str = "data/agents"):
        self.bot_id = bot_id
        self.data_dir = data_dir
        self.filepath = os.path.join(data_dir, f"{bot_id}.json")
        
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

    def save(self, memory: deque, locations: dict, long_term_memory: list = None):
        try:
            data = {
                "memory": list(memory),
                "locations": locations,
                "long_term_memory": long_term_memory or []
            }
            with open(self.filepath, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved state for {self.bot_id}")
        except Exception as e:
            logger.error(f"Failed to save state for {self.bot_id}: {e}")

    def load(self) -> tuple[deque, dict, list]:
        if not os.path.exists(self.filepath):
            return deque(maxlen=15), {}, []
        
        try:
            with open(self.filepath, 'r') as f:
                data = json.load(f)
            
            memory = deque(data.get("memory", []), maxlen=15)
            locations = data.get("locations", {})
            long_term_memory = data.get("long_term_memory", [])
            logger.info(f"Loaded state for {self.bot_id}")
            return memory, locations, long_term_memory
        except Exception as e:
            logger.error(f"Failed to load state for {self.bot_id}: {e}")
            return deque(maxlen=15), {}, []
