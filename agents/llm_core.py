import os
import logging
import json
import random
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from google.generativeai.types import FunctionDeclaration, Tool
from openai import OpenAI
from pydantic import TypeAdapter, ValidationError
from agents.grammar import (
    AgentAction, MoveAction, ChatAction, MineAction, CraftAction, EquipAction, IdleAction, 
    AttackAction, BuildStructure, PlaceBlock, InspectZone, ManageInventory, 
    BreakBlock, ThrowItem, UseItem, MountEntity, DismountEntity, Sleep, Wake, 
    StopAction, InteractAction, SaveLocation, Remember, ExploreAction, 
    BroadcastEvent, SpawnEvent, WeatherEvent, WaitEvent,
    GatherResource, HuntCreature, FindAndCollect,
    SmeltItem, ClearArea, DepositToChest, FarmLoop,
    ConfigureBehavior
)

logger = logging.getLogger(__name__)

ALL_ACTIONS = [
    MoveAction, ChatAction, MineAction, GatherResource, CraftAction, EquipAction, IdleAction, StopAction,
    AttackAction, HuntCreature, BuildStructure, PlaceBlock, InspectZone, ManageInventory, InteractAction,
    BreakBlock, ThrowItem, UseItem, FindAndCollect, MountEntity, DismountEntity, Sleep, Wake,
    SmeltItem, ClearArea, DepositToChest, FarmLoop, ConfigureBehavior,
    SaveLocation, Remember, ExploreAction
]

class LLMProvider(ABC):
    @abstractmethod
    def generate_response(self, system_prompt: str, user_prompt: str, tools: Optional[List[Any]] = None) -> Dict[str, Any]:
        """
        Generates a response from the LLM.
        """
        pass

def pydantic_to_gemini_tool(model):
    schema = model.model_json_schema()
    properties = {}
    for k, v in schema.get('properties', {}).items():
        prop_type = v.get('type')
        prop_type_str = "STRING" 
        if prop_type == 'integer': prop_type_str = "INTEGER"
        elif prop_type == 'number': prop_type_str = "NUMBER"
        elif prop_type == 'boolean': prop_type_str = "BOOLEAN"
        
        properties[k] = {
            "type": prop_type_str,
            "description": v.get('description', ''),
        }
        if 'enum' in v:
            properties[k]['enum'] = v['enum']

    return FunctionDeclaration(
        name=model.__name__,
        description=f"Perform a {model.__name__}",
        parameters={
            "type": "OBJECT",
            "properties": properties,
            "required": schema.get('required', [])
        }
    )

class GeminiLLM(LLMProvider):
    def __init__(self, api_key: str = None, model_name: str = "gemini-2.5-flash"):
        # Support multiple keys via comma-separated string
        keys_str = os.getenv("GEMINI_API_KEYS", "")
        self.api_keys = [k.strip() for k in keys_str.split(',') if k.strip()]
        
        # Fallback to single key
        single_key = api_key or os.getenv("GEMINI_API_KEY")
        if single_key and single_key not in self.api_keys:
            self.api_keys.append(single_key)
            
        if not self.api_keys:
            logger.warning("No GEMINI_API_KEYS or GEMINI_API_KEY found.")

        # Randomize start index to distribute load across processes
        self.current_key_index = random.randint(0, len(self.api_keys) - 1) if self.api_keys else 0
        self.model_name = model_name
        
        # Default Agent Tools
        self.default_tools = Tool(function_declarations=[pydantic_to_gemini_tool(m) for m in ALL_ACTIONS])
        self.tools = self.default_tools

    def _get_current_key(self):
        if not self.api_keys:
            return None
        return self.api_keys[self.current_key_index]

    def _rotate_key(self):
        if not self.api_keys:
            return
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        logger.info(f"Rotated Gemini API Key to index {self.current_key_index}")

    def generate_response(self, system_prompt: str, user_prompt: str, tools: Optional[List[Any]] = None) -> Dict[str, Any]:
        if not self.api_keys:
             return {"action": "IDLE", "reason": "Missing API Key"}

        active_tools = self.default_tools
        if tools:
            declarations = [pydantic_to_gemini_tool(m) for m in tools]
            active_tools = Tool(function_declarations=declarations)

        max_retries = 5
        base_delay = 2

        for attempt in range(max_retries):
            try:
                current_key = self._get_current_key()
                genai.configure(api_key=current_key)
                
                model = genai.GenerativeModel(self.model_name, tools=[active_tools])
                chat = model.start_chat()
                full_prompt = f"{system_prompt}\n\n{user_prompt}"
                
                response = chat.send_message(full_prompt)
                
                for part in response.parts:
                    if part.function_call:
                        fc = part.function_call
                        args = dict(fc.args)
                        name = fc.name
                        
                        # Mapping logic
                        if name == "AttackAction": args["action"] = "SET_COMBAT_MODE"
                        elif name == "ExploreAction": args["action"] = "SET_EXPLORATION_MODE"
                        elif name == "MoveAction": args["action"] = "MOVE"
                        elif name == "ChatAction": args["action"] = "CHAT"
                        elif name == "MineAction": args["action"] = "MINE"
                        elif name == "GatherResource": args["action"] = "GATHER"
                        elif name == "HuntCreature": args["action"] = "HUNT"
                        elif name == "FindAndCollect": args["action"] = "COLLECT_ITEM"
                        elif name == "SmeltItem": args["action"] = "SMELT"
                        elif name == "ClearArea": args["action"] = "CLEAR_AREA"
                        elif name == "DepositToChest": args["action"] = "DEPOSIT"
                        elif name == "FarmLoop": args["action"] = "FARM"
                        elif name == "ConfigureBehavior": args["action"] = "CONFIGURE"
                        elif name == "CraftAction": args["action"] = "CRAFT"
                        elif name == "EquipAction": args["action"] = "EQUIP"
                        elif name == "IdleAction": args["action"] = "IDLE"
                        elif name == "StopAction": args["action"] = "STOP"
                        elif name == "BuildStructure": args["action"] = "BUILD"
                        elif name == "PlaceBlock": args["action"] = "PLACE_BLOCK"
                        elif name == "InspectZone": args["action"] = "INSPECT_ZONE"
                        elif name == "ManageInventory": args["action"] = "INVENTORY"
                        elif name == "InteractAction": args["action"] = "INTERACT"
                        elif name == "BreakBlock": args["action"] = "BREAK_BLOCK"
                        elif name == "ThrowItem": args["action"] = "THROW_ITEM"
                        elif name == "UseItem": args["action"] = "USE_ITEM"
                        elif name == "MountEntity": args["action"] = "MOUNT"
                        elif name == "DismountEntity": args["action"] = "DISMOUNT"
                        elif name == "Sleep": args["action"] = "SLEEP"
                        elif name == "Wake": args["action"] = "WAKE"
                        elif name == "SaveLocation": args["action"] = "SAVE_LOCATION"
                        elif name == "Remember": args["action"] = "REMEMBER"
                        
                        # Narrator
                        elif name == "BroadcastEvent": args["action"] = "BROADCAST"
                        elif name == "SpawnEvent": args["action"] = "SPAWN"
                        elif name == "WeatherEvent": args["action"] = "WEATHER"
                        elif name == "WaitEvent": args["action"] = "WAIT"

                        return args
                
                return {"action": "IDLE", "reason": "No tool called"}

            except ResourceExhausted:
                logger.warning(f"Gemini Quota Exceeded on key ...{current_key[-4:]}. Rotating...")
                self._rotate_key()
                # If we have rotated back to start or just have 1 key, we must sleep
                time.sleep(base_delay * (attempt + 1))
            except Exception as e:
                logger.error(f"Gemini API Error: {e}")
                if "429" in str(e): # Handle generic 429 if not caught by ResourceExhausted
                    self._rotate_key()
                    time.sleep(base_delay * (attempt + 1))
                else:
                    return {"action": "IDLE", "reason": str(e)}
        
        return {"action": "IDLE", "reason": "Max Retries Exceeded"}

class OpenAILLM(LLMProvider):
    def __init__(self, api_key: str = None, model_name: str = "gpt-4o"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None
        self.model_name = model_name
        
        self.action_models = ALL_ACTIONS

    def generate_response(self, system_prompt: str, user_prompt: str, tools: Optional[List[Any]] = None) -> Dict[str, Any]:
        if not self.client:
             return {"action": "IDLE", "reason": "Missing API Key"}

        active_models = tools if tools else self.action_models
        
        openai_tools = []
        for model in active_models:
            schema = model.model_json_schema()
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": model.__name__,
                    "description": f"Perform a {model.__name__}",
                    "parameters": schema
                }
            })

        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=openai_tools,
                tool_choice="auto" 
            )

            message = response.choices[0].message
            if message.tool_calls:
                tool_call = message.tool_calls[0]
                action_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                
                # Manual Mapping (Same as Gemini)
                if action_name == "AttackAction": args["action"] = "SET_COMBAT_MODE"
                elif action_name == "ExploreAction": args["action"] = "SET_EXPLORATION_MODE"
                elif action_name == "MoveAction": args["action"] = "MOVE"
                elif action_name == "ChatAction": args["action"] = "CHAT"
                elif action_name == "MineAction": args["action"] = "MINE"
                elif action_name == "CraftAction": args["action"] = "CRAFT"
                elif action_name == "EquipAction": args["action"] = "EQUIP"
                elif action_name == "IdleAction": args["action"] = "IDLE"
                elif action_name == "StopAction": args["action"] = "STOP"
                elif action_name == "BuildStructure": args["action"] = "BUILD"
                elif action_name == "PlaceBlock": args["action"] = "PLACE_BLOCK"
                elif action_name == "InspectZone": args["action"] = "INSPECT_ZONE"
                elif action_name == "ManageInventory": args["action"] = "INVENTORY"
                elif action_name == "InteractAction": args["action"] = "INTERACT"
                elif action_name == "BreakBlock": args["action"] = "BREAK_BLOCK"
                elif action_name == "ThrowItem": args["action"] = "THROW_ITEM"
                elif action_name == "UseItem": args["action"] = "USE_ITEM"
                elif action_name == "MountEntity": args["action"] = "MOUNT"
                elif action_name == "DismountEntity": args["action"] = "DISMOUNT"
                elif action_name == "Sleep": args["action"] = "SLEEP"
                elif action_name == "Wake": args["action"] = "WAKE"
                elif action_name == "SaveLocation": args["action"] = "SAVE_LOCATION"
                elif action_name == "Remember": args["action"] = "REMEMBER"
                
                elif action_name == "BroadcastEvent": args["action"] = "BROADCAST"
                elif action_name == "SpawnEvent": args["action"] = "SPAWN"
                elif action_name == "WeatherEvent": args["action"] = "WEATHER"
                elif action_name == "WaitEvent": args["action"] = "WAIT"

                return args
            
            return {"action": "IDLE", "reason": "No tool called"}

        except Exception as e:
            logger.error(f"OpenAI API Error: {e}")
            return {"action": "IDLE", "reason": str(e)}

class MockLLM(LLMProvider):

    def generate_response(self, system_prompt: str, user_prompt: str, tools: Optional[List[Any]] = None) -> Dict[str, Any]:
        actions = [
            {"action": "CHAT", "message": "Simulating thought process..."},
            {"action": "MOVE", "target": "100 64 100"},
            {"action": "MINE", "block_name": "stone"},
            {"action": "IDLE", "reason": "Contemplating existence"},
            {"action": "INSPECT_ZONE", "c1": "0 60 0", "c2": "5 65 5"}
        ]
        return random.choice(actions)



class OllamaLLM(OpenAILLM):
    """
    Ollama implementation using the OpenAI-compatible API.
    """
    def __init__(self, base_url: str = None, model_name: str = "llama3.1", **kwargs):
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        self.api_key = "ollama" # Required dummy key
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        self.model_name = model_name
        
        self.action_models = ALL_ACTIONS

class LlamaCppLLM(OpenAILLM):
    """
    Llama.cpp server implementation using the OpenAI-compatible API.
    """
    def __init__(self, base_url: str = None, model_name: str = "default", **kwargs):
        self.base_url = base_url or os.getenv("LLAMACPP_BASE_URL", "http://localhost:8080/v1")
        self.api_key = "llamacpp" # Required dummy key
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        self.model_name = model_name
        
        self.action_models = ALL_ACTIONS

def get_llm_provider(provider_name: str, **kwargs) -> LLMProvider:
    if provider_name.lower() == "gemini":
        return GeminiLLM(**kwargs)
    elif provider_name.lower() == "openai":
        return OpenAILLM(**kwargs)
    elif provider_name.lower() == "ollama":
        return OllamaLLM(**kwargs)
    elif provider_name.lower() == "llamacpp":
        return LlamaCppLLM(**kwargs)
    return MockLLM()
