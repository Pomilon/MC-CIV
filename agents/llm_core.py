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
from openai import OpenAI, AzureOpenAI
import anthropic
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

# Mapping from Class Name to Action String
# This ensures we consistently inject the correct 'action' type even if the LLM omits the literal field.
ACTION_MAPPING = {
    "AttackAction": "SET_COMBAT_MODE",
    "ExploreAction": "SET_EXPLORATION_MODE",
    "MoveAction": "MOVE",
    "ChatAction": "CHAT",
    "MineAction": "MINE",
    "GatherResource": "GATHER",
    "HuntCreature": "HUNT",
    "FindAndCollect": "COLLECT_ITEM",
    "SmeltItem": "SMELT",
    "ClearArea": "CLEAR_AREA",
    "DepositToChest": "DEPOSIT",
    "FarmLoop": "FARM",
    "ConfigureBehavior": "CONFIGURE",
    "CraftAction": "CRAFT",
    "EquipAction": "EQUIP",
    "IdleAction": "IDLE",
    "StopAction": "STOP",
    "BuildStructure": "BUILD",
    "PlaceBlock": "PLACE_BLOCK",
    "InspectZone": "INSPECT_ZONE",
    "ManageInventory": "INVENTORY",
    "InteractAction": "INTERACT",
    "BreakBlock": "BREAK_BLOCK",
    "ThrowItem": "THROW_ITEM",
    "UseItem": "USE_ITEM",
    "MountEntity": "MOUNT",
    "DismountEntity": "DISMOUNT",
    "Sleep": "SLEEP",
    "Wake": "WAKE",
    "SaveLocation": "SAVE_LOCATION",
    "Remember": "REMEMBER",
    "BroadcastEvent": "BROADCAST",
    "SpawnEvent": "SPAWN",
    "WeatherEvent": "WEATHER",
    "WaitEvent": "WAIT"
}

class LLMProvider(ABC):
    @abstractmethod
    def generate_response(self, system_prompt: str, user_prompt: str, tools: Optional[List[Any]] = None) -> Dict[str, Any]:
        """
        Generates a response from the LLM.
        """
        pass

    def _map_tool_response(self, function_name: str, args: dict) -> dict:
        """Helper to inject the correct action string based on the function name."""
        if function_name in ACTION_MAPPING:
            args["action"] = ACTION_MAPPING[function_name]
        return args

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
    def __init__(self, api_key: str = None, model_name: str = "gemini-2.0-flash"):
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
                        return self._map_tool_response(name, args)
                
                return {"action": "IDLE", "reason": "No tool called"}

            except ResourceExhausted:
                logger.warning(f"Gemini Quota Exceeded on key ...{current_key[-4:]}. Rotating...")
                self._rotate_key()
                time.sleep(base_delay * (attempt + 1))
            except Exception as e:
                logger.error(f"Gemini API Error: {e}")
                if "429" in str(e): 
                    self._rotate_key()
                    time.sleep(base_delay * (attempt + 1))
                else:
                    return {"action": "IDLE", "reason": str(e)}
        
        return {"action": "IDLE", "reason": "Max Retries Exceeded"}

class OpenAILLM(LLMProvider):
    def __init__(self, api_key: str = None, base_url: str = None, model_name: str = "gpt-4o"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        
        if not self.api_key:
             # Some local providers (like Ollama) don't strictly need a key, but library might require one.
             self.api_key = "dummy" 
             
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        self.model_name = model_name
        self.action_models = ALL_ACTIONS

    def generate_response(self, system_prompt: str, user_prompt: str, tools: Optional[List[Any]] = None) -> Dict[str, Any]:
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
                return self._map_tool_response(action_name, args)
            
            return {"action": "IDLE", "reason": "No tool called"}

        except Exception as e:
            logger.error(f"OpenAI API Error: {e}")
            return {"action": "IDLE", "reason": str(e)}

class AnthropicLLM(LLMProvider):
    def __init__(self, api_key: str = None, model_name: str = "claude-3-5-sonnet-20241022"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.client = anthropic.Anthropic(api_key=self.api_key) if self.api_key else None
        self.model_name = model_name
        self.action_models = ALL_ACTIONS

    def generate_response(self, system_prompt: str, user_prompt: str, tools: Optional[List[Any]] = None) -> Dict[str, Any]:
        if not self.client:
             return {"action": "IDLE", "reason": "Missing API Key"}

        active_models = tools if tools else self.action_models
        
        claude_tools = []
        for model in active_models:
            schema = model.model_json_schema()
            claude_tools.append({
                "name": model.__name__,
                "description": f"Perform a {model.__name__}",
                "input_schema": schema
            })

        try:
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=1024,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ],
                tools=claude_tools
            )

            # Anthropic stop_reason for tools is 'tool_use'
            if response.stop_reason == "tool_use":
                # Find the tool use block
                for content in response.content:
                    if content.type == "tool_use":
                        action_name = content.name
                        args = content.input
                        return self._map_tool_response(action_name, args)
            
            return {"action": "IDLE", "reason": "No tool called"}

        except Exception as e:
            logger.error(f"Anthropic API Error: {e}")
            return {"action": "IDLE", "reason": str(e)}

class MockLLM(LLMProvider):
    def generate_response(self, system_prompt: str, user_prompt: str, tools: Optional[List[Any]] = None) -> Dict[str, Any]:
        user_prompt_lower = user_prompt.lower()
        
        if "build a house" in system_prompt.lower() or "build" in user_prompt_lower:
            return {
                "action": "BUILD",
                "shape": "cube",
                "material": "planks",
                "dimensions": "3 3 3",
                "location": "near_me"
            }
        
        if "explore" in user_prompt_lower:
             return {"action": "SET_EXPLORATION_MODE", "mode": "wander"}
             
        if "fight" in user_prompt_lower:
            return {"action": "SET_COMBAT_MODE", "mode": "pvp", "target": "Zombie"}

        actions = [
            {"action": "CHAT", "message": "I am operating in MOCK MODE."},
            {"action": "MOVE", "target": "100 64 100"},
            {"action": "MINE", "block_name": "stone"},
            {"action": "IDLE", "reason": "Simulated wait"},
        ]
        return random.choice(actions)

def get_llm_provider(provider_name: str, **kwargs) -> LLMProvider:
    if os.getenv("MOCK_MODE", "").lower() == "true":
        logger.info("MOCK_MODE enabled. Forcing MockLLM.")
        return MockLLM()

    provider_name = provider_name.lower()
    
    if provider_name == "gemini":
        return GeminiLLM(**kwargs)
    elif provider_name == "openai":
        return OpenAILLM(**kwargs)
    elif provider_name == "anthropic" or provider_name == "claude":
        return AnthropicLLM(**kwargs)
    elif provider_name == "ollama":
        # Defaults for Ollama
        if "base_url" not in kwargs:
            kwargs["base_url"] = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        if "model_name" not in kwargs:
            kwargs["model_name"] = "llama3.1"
        return OpenAILLM(**kwargs)
    elif provider_name == "llamacpp":
        # Defaults for LlamaCpp
        if "base_url" not in kwargs:
            kwargs["base_url"] = os.getenv("LLAMACPP_BASE_URL", "http://localhost:8080/v1")
        if "model_name" not in kwargs:
            kwargs["model_name"] = "default"
        return OpenAILLM(**kwargs)
    elif provider_name == "groq":
        if "base_url" not in kwargs:
            kwargs["base_url"] = "https://api.groq.com/openai/v1"
        if "model_name" not in kwargs:
            kwargs["model_name"] = "llama3-70b-8192"
        return OpenAILLM(**kwargs)
        
    return MockLLM()