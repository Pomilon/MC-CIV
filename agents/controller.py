import time
import requests
import logging
import json
from collections import deque
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from agents.llm_core import LLMProvider
from agents.storage import StorageManager

logger = logging.getLogger(__name__)

class AgentController:
    def __init__(self, bot_url: str, llm: LLMProvider, mission: str, bot_id: str = "Bot1"):
        self.bot_url = bot_url
        self.llm = llm
        self.mission = mission
        self.bot_id = bot_id
        self.last_action_status = "success"
        
        # Persistence
        self.storage = StorageManager(bot_id)
        self.memory, self.locations = self.storage.load()

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1), retry=retry_if_exception_type(requests.RequestException))
    def observe(self):
        try:
            response = requests.get(f"{self.bot_url}/observe", timeout=2)
            if response.status_code == 200:
                return response.json()
        except requests.RequestException as e:
            logger.warning(f"Observe failed (retrying): {e}")
            raise e
        return None

    def reason(self, observation):
        chat_log = "\n".join([f"{c['username']}: {c['message']}" for c in observation.get('chat_history', [])])
        memory_str = "\n".join([f"- {m}" for m in self.memory])
        behavior_state = observation.get('behavior_state', {})
        
        locations_str = ", ".join([f"{k}: {v}" for k, v in self.locations.items()])
        
        system_prompt = f"""
        You are an intelligent Minecraft COMMANDER.
        Your GLOBAL MISSION is: {self.mission}.
        
        You control a bot that has AUTONOMOUS capabilities.
        
        COMMANDS AVAILABLE:
        - SET_COMBAT_MODE (mode="pvp"|"none", target="...")
        - SET_SURVIVAL (preset="brave"|"cowardly"|"neutral")
        - BUILD (structure_type="wall", location="...")
        - INVENTORY (task="equip_best"|"sort"|"discard_junk")
        - MOVE (target="Name" or "x y z")
        - SAVE_LOCATION (name="...") -> Remembers current position.
        - SET_EXPLORATION_MODE (mode="wander"|"follow"|"stop", target="...")
        - MINE/CRAFT/CHAT
        
        KNOWN LOCATIONS: {locations_str}
        
        CURRENT STATE:
        - Combat: {behavior_state.get('combatMode')}
        - Explore: {behavior_state.get('explorationMode')}
        
        GUIDELINES:
        1. To explore, use SET_EXPLORATION_MODE.
        2. To go to a saved location, use MOVE with the location name.
        
        Your previous action status was: {self.last_action_status}.
        """
        
        user_prompt = f"""
        OBSERVATION:
        - Pos: {observation.get('position')}
        - Health: {observation.get('health')}
        - Food: {observation.get('food')}
        - Inventory: {observation.get('inventory')}
        - Nearby Entities: {observation.get('nearby_entities')}
        - Nearby Blocks: {observation.get('nearby_blocks')}
        
        RECENT CHAT:
        {chat_log}
        
        RECENT MEMORY:
        {memory_str}
        
        What is your reasoning and next COMMAND?
        """
        
        action_dict = self.llm.generate_response(system_prompt, user_prompt)
        return action_dict

    def act(self, action_dict):
        logger.info(f"Agent Command: {action_dict}")
        
        action_type = action_dict.get('action')
        
        if action_type == 'SAVE_LOCATION':
            obs = self.observe_safe() # Use non-raising version or cached?
            # Ideally observe() is called once per loop.
            # But here we need fresh coords if not passed.
            # Let's assume we use the last observation from the loop?
            # Refactor: `act` should probably receive the current observation context.
            # For robustness, let's fetch strictly.
            try:
                obs = self.observe()
            except:
                obs = None
                
            if obs and 'position' in obs:
                p = obs['position']
                coords = f"{int(p['x'])} {int(p['y'])} {int(p['z'])}"
                name = action_dict.get('name')
                self.locations[name] = coords
                self.memory.append(f"Saved location '{name}' at {coords}")
                self.storage.save(self.memory, self.locations)
                return 
        
        elif action_type == 'MOVE':
            target = action_dict.get('target')
            if target in self.locations:
                action_dict['target'] = self.locations[target]
                self.memory.append(f"Resolved '{target}' to {action_dict['target']}")

        self.memory.append(f"Command: {action_dict}")
        self.storage.save(self.memory, self.locations)
        
        try:
            self._send_command(action_dict)
        except Exception as e:
            logger.error(f"Failed to act: {e}")
            self.last_action_status = "network_exception"

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1), retry=retry_if_exception_type(requests.RequestException))
    def _send_command(self, action_dict):
        response = requests.post(f"{self.bot_url}/act", json=action_dict, timeout=5)
        if response.status_code == 200:
            res_data = response.json()
            self.last_action_status = res_data.get('status', 'unknown')
            if self.last_action_status == 'failed':
                self.memory.append(f"Command Failed: {res_data.get('reason')}")
        else:
            self.last_action_status = "network_error"

    def observe_safe(self):
        try:
            return self.observe()
        except:
            return None

    def run_loop(self, interval=5):
        logger.info(f"Starting Agent Loop for mission: {self.mission}")
        while True:
            try:
                obs = self.observe_safe()
                if obs:
                    action = self.reason(obs)
                    self.act(action)
                else:
                    logger.warning("No observation received. Is bot client running?")
            except Exception as e:
                logger.error(f"Error in Agent Loop: {e}")
            time.sleep(interval)
