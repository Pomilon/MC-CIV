# Update LLMProvider to support new tools
import os
import logging
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool
from openai import OpenAI
from agents.grammar import (
    MoveAction, ChatAction, MineAction, CraftAction, EquipAction, IdleAction,
    SetCombatMode, SetSurvivalPreset, BuildStructure, ManageInventory,
    SaveLocation, SetExplorationMode
)

logger = logging.getLogger(__name__)

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
    def __init__(self, api_key: str = None, model_name: str = "gemini-2.0-flash-exp"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
        self.model_name = model_name
        
        # Default Agent Tools
        action_models = [
            MoveAction, ChatAction, MineAction, CraftAction, EquipAction, IdleAction,
            SetCombatMode, SetSurvivalPreset, BuildStructure, ManageInventory,
            SaveLocation, SetExplorationMode
        ]
        self.default_tools = Tool(function_declarations=[pydantic_to_gemini_tool(m) for m in action_models])
        self.tools = self.default_tools

    def generate_response(self, system_prompt: str, user_prompt: str, tools: Optional[List[Any]] = None) -> Dict[str, Any]:
        if not self.api_key:
             return {"action": "IDLE", "reason": "Missing API Key"}

        try:
            active_tools = self.default_tools
            if tools:
                declarations = [pydantic_to_gemini_tool(m) for m in tools]
                active_tools = Tool(function_declarations=declarations)

            model = genai.GenerativeModel(self.model_name, tools=[active_tools])
            chat = model.start_chat()
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            
            response = chat.sendMessage(full_prompt)
            
            for part in response.parts:
                if part.function_call:
                    fc = part.function_call
                    args = dict(fc.args)
                    
                    # Explicit mapping for ALL tools
                    name = fc.name
                    if name == "MoveAction": args["action"] = "MOVE"
                    elif name == "ChatAction": args["action"] = "CHAT"
                    elif name == "MineAction": args["action"] = "MINE"
                    elif name == "CraftAction": args["action"] = "CRAFT"
                    elif name == "EquipAction": args["action"] = "EQUIP"
                    elif name == "IdleAction": args["action"] = "IDLE"
                    
                    elif name == "SetCombatMode": args["action"] = "SET_COMBAT_MODE"
                    elif name == "SetSurvivalPreset": args["action"] = "SET_SURVIVAL"
                    elif name == "BuildStructure": args["action"] = "BUILD"
                    elif name == "ManageInventory": args["action"] = "INVENTORY"
                    
                    elif name == "SaveLocation": args["action"] = "SAVE_LOCATION"
                    elif name == "SetExplorationMode": args["action"] = "SET_EXPLORATION_MODE"
                    
                    elif name == "BroadcastEvent": args["action"] = "BROADCAST"
                    elif name == "SpawnEvent": args["action"] = "SPAWN"
                    elif name == "WeatherEvent": args["action"] = "WEATHER"
                    elif name == "WaitEvent": args["action"] = "WAIT"

                    return args
            
            return {"action": "IDLE", "reason": "No tool called"}

        except Exception as e:
            logger.error(f"Gemini API Error: {e}")
            return {"action": "IDLE", "reason": str(e)}

class OpenAILLM(LLMProvider):
    def __init__(self, api_key: str = None, model_name: str = "gpt-4o"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None
        self.model_name = model_name

    def generate_response(self, system_prompt: str, user_prompt: str, tools: Optional[List[Any]] = None) -> Dict[str, Any]:
        if not self.client:
             return {"action": "IDLE", "reason": "Missing API Key"}

        # Define tools based on default or passed models
        active_models = tools if tools else [
            MoveAction, ChatAction, MineAction, CraftAction, EquipAction, IdleAction,
            SetCombatMode, SetSurvivalPreset, BuildStructure, ManageInventory,
            SaveLocation, SetExplorationMode
        ]
        
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
                
                # Explicit mapping
                if action_name == "MoveAction": args["action"] = "MOVE"
                elif action_name == "ChatAction": args["action"] = "CHAT"
                elif action_name == "MineAction": args["action"] = "MINE"
                elif action_name == "CraftAction": args["action"] = "CRAFT"
                elif action_name == "EquipAction": args["action"] = "EQUIP"
                elif action_name == "IdleAction": args["action"] = "IDLE"

                elif action_name == "SetCombatMode": args["action"] = "SET_COMBAT_MODE"
                elif action_name == "SetSurvivalPreset": args["action"] = "SET_SURVIVAL"
                elif action_name == "BuildStructure": args["action"] = "BUILD"
                elif action_name == "ManageInventory": args["action"] = "INVENTORY"
                
                elif action_name == "SaveLocation": args["action"] = "SAVE_LOCATION"
                elif action_name == "SetExplorationMode": args["action"] = "SET_EXPLORATION_MODE"
                
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
        return {"action": "CHAT", "message": "Mock Response"}

def get_llm_provider(provider_name: str, **kwargs) -> LLMProvider:
    if provider_name.lower() == "gemini":
        return GeminiLLM(**kwargs)
    elif provider_name.lower() == "openai":
        return OpenAILLM(**kwargs)
    return MockLLM()
