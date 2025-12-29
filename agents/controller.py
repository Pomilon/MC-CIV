import time
import requests
import logging
import json
import os
from collections import deque
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from agents.llm_core import LLMProvider
from agents.storage import StorageManager

logger = logging.getLogger(__name__)

class AgentController:
    def __init__(self, bot_url: str, llm: LLMProvider, mission: str, bot_id: str = "Bot1", profile_path: str = None):
        self.bot_url = bot_url
        self.llm = llm
        self.mission = mission
        self.bot_id = bot_id
        self.current_action_id = None
        
        # Load Profile
        self.profile = {}
        if profile_path and os.path.exists(profile_path):
            try:
                with open(profile_path, 'r') as f:
                    self.profile = json.load(f)
                logger.info(f"Loaded profile from {profile_path}")
            except Exception as e:
                logger.error(f"Failed to load profile: {e}")
        
        # Fallback if profile missing
        if not self.profile:
            base_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'profiles', 'base.json')
            if os.path.exists(base_path):
                 with open(base_path, 'r') as f:
                    self.profile = json.load(f)
            else:
                self.profile = {
                    "persona": "You are a standard Minecraft Bot.",
                    "system_template": "{persona}\nMission: {mission}\n\nCOMMANDS:\n{command_docs}\n\nLocations: {locations}\nLast Result: {last_result}",
                    "command_docs": "Standard Commands Available."
                }

        # Persistence
        self.storage = StorageManager(bot_id)
        self.memory, self.locations, self.long_term_memory = self.storage.load()

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

    def _get_feedback_hint(self, error):
        error = str(error).lower()
        if "itemnotininventory" in error or "missing item" in error:
            return " -> HINT: Check your inventory. You may need to MINE, GATHER, or CRAFT the item first."
        if "blocknotfound" in error or "targetisair" in error:
            return " -> HINT: The target block was not found nearby. Try to MOVE to a different location or EXPLORE."
        if "targetnotfound" in error or "entitynotfound" in error:
            return " -> HINT: The entity is not nearby. Use SET_EXPLORATION_MODE to find it."
        if "nopath" in error or "unreachable" in error:
            return " -> HINT: The bot cannot reach the target. It might be blocked. Try clearing the way or moving closer."
        if "recipe" in error:
            return " -> HINT: You are missing resources or the recipe does not exist. Check requirements."
        if "dimensions" in error:
            return " -> HINT: Dimensions must be 'W H D' (integers)."
        if "unknown item" in error or "unknown block" in error:
            return " -> HINT: The item/block name might be misspelled or invalid. Check the name."
        return ""

    def reason(self, observation, action_state):
        chat_log = "\n".join([f"{c['username']}: {c['message']}" for c in observation.get('chat_history', [])][-10:])
        # Convert deque to list for slicing/iteration safety
        memory_str = "\n".join([f"- {m}" for m in list(self.memory)[-15:]]) 
        # Limit long term memory to avoid token explosion
        long_term_str = "\n".join([f"- {m}" for m in self.long_term_memory[-20:]])
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
                hint = self._get_feedback_hint(error)
                last_result = f"FAILURE: {error} (Partial: {signal}){hint}"
            elif status == 'idle':
                last_result = "IDLE"

        # Construct System Prompt from Profile
        template = self.profile.get("system_template", "")
        persona = self.profile.get("persona", "You are a Minecraft Bot.")
        command_docs = self.profile.get("command_docs", "Use available tools.")
        
        # Safe format
        system_prompt = template.format(
            persona=persona,
            mission=self.mission,
            command_docs=command_docs,
            locations=locations_str,
            last_result=last_result
        )
        
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
        
        LONG TERM MEMORY:
        {long_term_str}

        RECENT ACTION LOG:
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
            try:
                obs = self.observe()
                if obs and 'position' in obs:
                    p = obs['position']
                    coords = f"{int(p['x'])} {int(p['y'])} {int(p['z'])}"
                    name = action_dict.get('name')
                    self.locations[name] = coords
                    self.memory.append(f"Saved location '{name}' at {coords}")
                    self.storage.save(self.memory, self.locations, self.long_term_memory)
            except:
                pass
            return None # No bot action needed

        if action_type == 'REMEMBER':
            fact = action_dict.get('fact')
            if fact:
                self.long_term_memory.append(fact)
                self.memory.append(f"Remembered: {fact}")
                self.storage.save(self.memory, self.locations, self.long_term_memory)
            return None

        # Resolve Targets
        if action_type == 'MOVE':
            target = action_dict.get('target')
            if target in self.locations:
                action_dict['target'] = self.locations[target]

        self.memory.append(f"Command: {action_dict}")
        self.storage.save(self.memory, self.locations, self.long_term_memory)
        
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

    def run_loop(self, interval=5):
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
