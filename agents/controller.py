import asyncio
import json
import logging
import os
from collections import deque
from typing import Dict, Any, Optional
import websockets
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from agents.llm_core import LLMProvider
from agents.storage import StorageManager

logger = logging.getLogger(__name__)

class AgentController:
    def __init__(self, bot_url: str, llm: LLMProvider, mission: str, bot_id: str = "Bot1", profile_path: str = None):
        self.bot_url = bot_url
        self.bot_id = bot_id
        self.mission = mission
        self.llm = llm
        
        # State
        self.state = "IDLE" # IDLE, PLANNING, EXECUTING
        self.latest_observation = None
        self.action_state = {"status": "idle"}
        self.websocket: Optional[WebSocket] = None
        
        # Load Profile
        self.profile = {}
        if profile_path and os.path.exists(profile_path):
            try:
                with open(profile_path, 'r') as f:
                    self.profile = json.load(f)
                logger.info(f"Loaded profile from {profile_path}")
            except Exception as e:
                logger.error(f"Failed to load profile: {e}")
        
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

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(requests.exceptions.ConnectionError),
        reraise=True
    )
    def observe(self):
        """Synchronous observation for tests/polling mode."""
        try:
            r = requests.get(f"{self.bot_url}/observe", timeout=5)
            if r.status_code == 200:
                self.latest_observation = r.json()
                return self.latest_observation
        except requests.exceptions.ConnectionError:
            # Re-raise for tenacity to catch
            raise
        except Exception as e:
            logger.error(f"Observe error: {e}")
            raise
        return None

    def act(self, action: Dict[str, Any]):
        """Synchronous action for tests/polling mode."""
        try:
            r = requests.post(f"{self.bot_url}/act", json=action, timeout=5)
            if r.status_code == 200:
                data = r.json()
                return data.get("action_id")
        except Exception as e:
            logger.error(f"Act error: {e}")
            raise
        return None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.websocket = websocket
        logger.info(f"Bot {self.bot_id} connected via WebSocket.")

    async def disconnect(self):
        self.websocket = None
        logger.info(f"Bot {self.bot_id} disconnected.")

    async def handle_message(self, data: Dict[str, Any]):
        msg_type = data.get("type")
        payload = data.get("data")

        if msg_type == "connect":
            logger.info(f"Bot Handshake: {payload}")
            
        elif msg_type == "observation":
            self.latest_observation = payload
            await self.process_observation()

        elif msg_type == "action_update":
            self.action_state = payload
            logger.info(f"Action Update: {payload['status']} - {payload.get('endSignal')}")
            if payload['status'] in ['completed', 'failed']:
                self.state = "IDLE"
                # Trigger re-evaluation immediately or wait for next observation
                # We'll wait for next observation to keep it simple and paced
                
        elif msg_type == "chat":
            logger.info(f"Chat: {payload['username']}: {payload['message']}")

    async def send_command(self, action: Dict[str, Any]):
        if self.websocket:
            await self.websocket.send_json({"type": "command", "data": action})
            self.state = "EXECUTING"

    async def dashboard_reporter(self):
        # Allow configuring dashboard URL via env
        dashboard_host = os.getenv("DASHBOARD_HOST", "localhost")
        dashboard_port = os.getenv("DASHBOARD_PORT", "8000")
        uri = f"ws://{dashboard_host}:{dashboard_port}/ws/agent/{self.bot_id}"
        
        while True:
            try:
                async with websockets.connect(uri) as websocket:
                    logger.info(f"Connected to Dashboard as {self.bot_id}")
                    while True:
                        if self.latest_observation:
                            # Enrich observation with current internal state
                            data = self.latest_observation.copy()
                            data['internal_state'] = self.state
                            await websocket.send(json.dumps(data))
                        await asyncio.sleep(2) 
            except Exception as e:
                # logger.warning(f"Dashboard connection failed: {e}")
                await asyncio.sleep(5)

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
        return ""

    async def process_observation(self):
        if self.state == "EXECUTING":
            # If we are executing, we check if the action is still running.
            # The 'action_state' update should handle the transition back to IDLE.
            # But just in case, we can check the observation's action_state too.
            obs_action_state = self.latest_observation.get("action_state", {})
            if obs_action_state.get("status") in ["completed", "failed"]:
                self.state = "IDLE"
            else:
                return # Still busy

        if self.state == "PLANNING":
            return # Already thinking

        # State is IDLE, let's reason
        self.state = "PLANNING"
        
        try:
            action = await asyncio.to_thread(self.reason, self.latest_observation)
            if action:
                if action.get("action") in ["SAVE_LOCATION", "REMEMBER"]:
                    # Internal actions
                    self.handle_internal_action(action)
                    self.state = "IDLE"
                else:
                    await self.send_command(action)
            else:
                self.state = "IDLE"
        except Exception as e:
            logger.error(f"Reasoning Error: {e}")
            self.state = "IDLE"

    def handle_internal_action(self, action):
        if action.get("action") == 'SAVE_LOCATION':
             p = self.latest_observation.get('position')
             if p:
                coords = f"{int(p['x'])} {int(p['y'])} {int(p['z'])}"
                name = action.get('name')
                self.locations[name] = coords
                self.memory.append(f"Saved location '{name}' at {coords}")
                self.storage.save(self.memory, self.locations, self.long_term_memory)

        elif action.get("action") == 'REMEMBER':
            fact = action.get('fact')
            if fact:
                self.long_term_memory.append(fact)
                self.memory.append(f"Remembered: {fact}")
                self.storage.save(self.memory, self.locations, self.long_term_memory)

    def reason(self, observation):
        chat_log = "\n".join([f"{c['username']}: {c['message']}" for c in observation.get('chat_history', [])][-10:])
        memory_str = "\n".join([f"- {m}" for m in list(self.memory)[-15:]]) 
        long_term_str = "\n".join([f"- {m}" for m in self.long_term_memory[-20:]])
        locations_str = ", ".join([f"{k}: {v}" for k, v in self.locations.items()])
        
        last_result = "None (Startup)"
        # Use the latest action state from observation or our internal tracker
        action_state = observation.get('action_state', self.action_state)
        
        status = action_state.get('status')
        signal = action_state.get('endSignal')
        error = action_state.get('error')
        data = action_state.get('data')
        
        zone_report = ""
        if status == 'completed':
            if signal == "ZoneInspected" and data:
                origin = data.get('origin', {})
                layers = data.get('layers', [])
                zone_report = f"\nZONE INSPECTION (Origin: {origin.get('x')}, {origin.get('y')}, {origin.get('z')}):\n"
                for y_idx, layer in enumerate(layers):
                    abs_y = origin.get('y', 0) + y_idx
                    zone_report += f"--- Layer Y+{y_idx} (Abs {abs_y}) ---\n"
                    for z_idx, row in enumerate(layer):
                        zone_report += f"Z+{z_idx}: {row}\n"
                last_result = f"INSPECT RESULT: {len(layers)} layers processed."
            else:
                last_result = f"SUCCESS: {signal}"
        elif status == 'failed':
            hint = self._get_feedback_hint(error)
            last_result = f"FAILURE: {error} (Partial: {signal}){hint}"
        elif status == 'idle':
            last_result = "IDLE"

        template = self.profile.get("system_template", "")
        persona = self.profile.get("persona", "You are a Minecraft Bot.")
        command_docs = self.profile.get("command_docs", "Use available tools.")
        
        system_prompt = template.format(
            persona=persona,
            mission=self.mission,
            command_docs=command_docs,
            locations=locations_str,
            last_result=last_result
        )
        if zone_report:
            system_prompt += zone_report
        
        user_prompt = f"""
        OBSERVATION:
        - Pos: {observation.get('position')}
        - Health: {observation.get('health')}
        - Food: {observation.get('food')}
        - Inventory: {observation.get('inventory')}
        - Nearby Entities: {observation.get('nearby_entities')}
        - Nearby Blocks: {observation.get('nearby_blocks')}
        - Time: {observation.get('time')}
        
        RECENT CHAT:
        {chat_log}
        
        LONG TERM MEMORY:
        {long_term_str}

        RECENT ACTION LOG:
        {memory_str}
        
        What is your reasoning and next COMMAND?
        """
        
        action_dict = self.llm.generate_response(system_prompt, user_prompt)
        
        # Post-processing
        if action_dict.get('action') == 'MOVE':
            target = action_dict.get('target')
            if target in self.locations:
                action_dict['target'] = self.locations[target]
                
        self.memory.append(f"Command: {action_dict}")
        self.storage.save(self.memory, self.locations, self.long_term_memory)
        
        return action_dict

def create_app(controller: AgentController):
    app = FastAPI()

    @app.on_event("startup")
    async def startup_event():
        asyncio.create_task(controller.dashboard_reporter())

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await controller.connect(websocket)
        try:
            while True:
                data = await websocket.receive_json()
                await controller.handle_message(data)
        except WebSocketDisconnect:
            await controller.disconnect()
        except Exception as e:
            logger.error(f"WebSocket Error: {e}")
            await controller.disconnect()
            
    return app
