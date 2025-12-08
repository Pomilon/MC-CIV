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
        self.current_action_id = None
        
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

    def reason(self, observation, action_state):
        chat_log = "\n".join([f"{c['username']}: {c['message']}" for c in observation.get('chat_history', [])])
        # Convert deque to list for slicing/iteration safety
        memory_str = "\n".join([f"- {m}" for m in list(self.memory)[-15:]]) 
        locations_str = ", ".join([f"{k}: {v}" for k, v in self.locations.items()])
        
        last_result = "None (Startup)"
        if action_state:
            status = action_state.get('status')
            signal = action_state.get('endSignal')
            error = action_state.get('error')
            data = action_state.get('data')
            
            if status == 'completed':
                if signal == "ZoneInspected" and data:
                    # Format as slices
                    origin = data.get('origin', {})
                    layers = data.get('layers', [])
                    
                    viz_lines = [f"ZONE INSPECTION (Origin: {origin.get('x')}, {origin.get('y')}, {origin.get('z')}):"]
                    
                    for y, layer in enumerate(layers):
                        abs_y = origin.get('y', 0) + y
                        viz_lines.append(f"--- Layer Y+{y} (Abs {abs_y}) ---")
                        for z, row in enumerate(layer):
                            row_str = ", ".join(row)
                            viz_lines.append(f"Z+{z}: [{row_str}]")
                            
                    last_result = "\n".join(viz_lines)
                else:
                    last_result = f"SUCCESS: {signal}"
            elif status == 'failed':
                last_result = f"FAILURE: {error} (Partial: {signal})"
            elif status == 'idle':
                last_result = "IDLE"

        system_prompt = f"""
        You are an intelligent Minecraft COMMANDER.
        Your GLOBAL MISSION is: {self.mission}.
        
        You control a bot that has AUTONOMOUS capabilities.
        
        COMMANDS AVAILABLE:
        - SET_COMBAT_MODE (mode="pvp"|"none", target="...") -> ATTACKS target until death or retreat.
        - BUILD (structure_type="wall"|"floor"|"shelter"|"tower", location="...")
        - PLACE_BLOCK (block_name="...", position="x y z" OR near_block="...")
        - BREAK_BLOCK (block_name="...", position="x y z"?) -> Pos takes precedence.
        - INSPECT_ZONE (corner1="x y z", corner2="x y z") -> Returns list of blocks in area.
        - INVENTORY (task="equip_best"|"sort"|"discard_junk")
        - MOVE (target="Name" or "x y z")
        - THROW_ITEM (item_name="...", count=1)
        - USE_ITEM (item_name="...") -> Eat/Drink/Use.
        - MOUNT (target="...") / DISMOUNT
        - SLEEP / WAKE
        - SAVE_LOCATION (name="...") -> Remembers current position.
        - SET_EXPLORATION_MODE (mode="wander"|"follow"|"stop", target="...")
        - MINE (block_name="...") / CRAFT (item_name="...")
        - INTERACT (target_block="...") -> Use block (chest, lever, etc).
        - CHAT (message="...")
        - STOP -> Interrupts current action.
        
        KNOWN LOCATIONS: {locations_str}
        
        LAST ACTION RESULT: {last_result}
        
        GUIDELINES:
        1. If last action FAILED, try a different approach or fix the issue.
        2. If last action SUCCESS, proceed to next step of mission.
        3. Do not repeat the same failed command endlessly.
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
        
        # Handle Local Memory Actions
        if action_type == 'SAVE_LOCATION':
            # We need current position.
            # We can't blocking observe here easily without refactor, 
            # but usually we have just observed. 
            # Ideally reason() should have passed the relevant coords context or we fetch it.
            # For now, let's just observe quickly.
            try:
                obs = self.observe()
                if obs and 'position' in obs:
                    p = obs['position']
                    coords = f"{int(p['x'])} {int(p['y'])} {int(p['z'])}"
                    name = action_dict.get('name')
                    self.locations[name] = coords
                    self.memory.append(f"Saved location '{name}' at {coords}")
                    self.storage.save(self.memory, self.locations)
            except:
                pass
            return None # No bot action needed

        # Resolve Targets
        if action_type == 'MOVE':
            target = action_dict.get('target')
            if target in self.locations:
                action_dict['target'] = self.locations[target]

        self.memory.append(f"Command: {action_dict}")
        self.storage.save(self.memory, self.locations)
        
        try:
            return self._send_command(action_dict)
        except Exception as e:
            logger.error(f"Failed to act: {e}")
            return None

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1), retry=retry_if_exception_type(requests.RequestException))
    def _send_command(self, action_dict):
        response = requests.post(f"{self.bot_url}/act", json=action_dict, timeout=5)
        if response.status_code == 200:
            res_data = response.json()
            return res_data.get('action_id')
        return None

    def observe_safe(self):
        try:
            return self.observe()
        except Exception:
            return None

    def observe_safe(self):
        try:
            return self.observe()
        except Exception:
            return None

    def run_loop(self, interval=2):
        logger.info(f"Starting Agent Loop for mission: {self.mission}")
        while True:
            try:
                obs = self.observe_safe()
                if obs:
                    action_state = obs.get('action_state', {})
                    status = action_state.get('status', 'idle')
                    
                    if status == 'running':
                        # Action is still running, wait.
                        pass
                    else:
                        try:
                            action = self.reason(obs, action_state)
                            if action:
                                new_id = self.act(action)
                                if new_id:
                                    self.current_action_id = new_id
                                    time.sleep(0.5) 
                        except Exception as e:
                            logger.error(f"Reasoning/Acting Error: {e}")
                            # Prevent hot-looping on error
                            time.sleep(2)
                else:
                    logger.warning("Bot unavailable (Booting or Disconnected)... waiting.")
                    time.sleep(5) # Wait longer if bot is down
                    
            except Exception as e:
                logger.critical(f"Critical Error in Agent Loop: {e}")
                time.sleep(5)
            
            time.sleep(interval)
