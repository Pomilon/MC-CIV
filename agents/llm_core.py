import json
import logging
import os
import random
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import anthropic
from google import genai
from google.genai import types
from openai import OpenAI

from agents import config
from agents.grammar import (
    BREAK_BLOCK,
    BUILD,
    CHAT,
    CLEAR_AREA,
    COLLECT_ITEM,
    CONFIGURE,
    CRAFT,
    DEPOSIT,
    DISMOUNT,
    EQUIP,
    FARM,
    GATHER,
    HUNT,
    IDLE,
    INSPECT_ZONE,
    INTERACT,
    INVENTORY,
    MINE,
    MOUNT,
    MOVE,
    PLACE_BLOCK,
    REMEMBER,
    SAVE_LOCATION,
    SET_COMBAT_MODE,
    SET_EXPLORATION_MODE,
    SLEEP,
    SMELT,
    STOP,
    THROW_ITEM,
    USE_ITEM,
    WAKE,
)

logger = logging.getLogger(__name__)

ALL_ACTIONS = [
    MOVE, CHAT, MINE, GATHER, CRAFT, EQUIP, IDLE, STOP,
    SET_COMBAT_MODE, HUNT, BUILD, PLACE_BLOCK, INSPECT_ZONE, INVENTORY, INTERACT,
    BREAK_BLOCK, THROW_ITEM, USE_ITEM, COLLECT_ITEM, MOUNT, DISMOUNT, SLEEP, WAKE,
    SMELT, CLEAR_AREA, DEPOSIT, FARM, CONFIGURE,
    SAVE_LOCATION, REMEMBER, SET_EXPLORATION_MODE
]

def pydantic_to_gemini_tool(model) -> types.FunctionDeclaration:
    schema = model.model_json_schema()
    schema.pop("title", None)
    props = schema.get("properties", {})
    props.pop("action", None)
    if "required" in schema:
        schema["required"] = [r for r in schema["required"] if r != "action"]
    return types.FunctionDeclaration(
        name=model.__name__,
        description=f"Perform a {model.__name__}",
        parameters=schema,
    )

class LLMProvider(ABC):
    @abstractmethod
    def generate_response(self, messages: List[Dict[str, Any]], tools: Optional[List[Any]] = None) -> Dict[str, Any]:
        """
        Generates a response from the LLM based on a conversation history.
        """
        pass

    def _map_tool_response(self, function_name: str, args: dict) -> dict:
        args["action"] = function_name
        return args

class OpenAILLM(LLMProvider):
    def __init__(self, api_key: str = None, base_url: str = None, model_name: str = "gpt-4o"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "dummy")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        self.model_name = model_name
        self.action_models = ALL_ACTIONS

    def generate_response(self, messages: List[Dict[str, Any]], tools: Optional[List[Any]] = None) -> Dict[str, Any]:
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
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=openai_tools,
                tool_choice="auto"
            )

            message = response.choices[0].message
            thought = message.content or ""

            if message.tool_calls:
                tool_call = message.tool_calls[0]
                action_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                result = self._map_tool_response(action_name, args)
                result["thought"] = thought
                result["tool_call_id"] = tool_call.id
                return result

            # Fallback to pure chat if no tool was called
            return {"action": "IDLE", "thought": thought, "reason": "No tool called"}

        except Exception as e:
            logger.error(f"OpenAI API Error: {e}")
            return {"action": "IDLE", "reason": str(e)}

class AnthropicLLM(LLMProvider):
    def __init__(self, api_key: str = None, model_name: str = "claude-3-5-sonnet-20241022"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.client = anthropic.Anthropic(api_key=self.api_key) if self.api_key else None
        self.model_name = model_name
        self.action_models = ALL_ACTIONS

    def generate_response(self, messages: List[Dict[str, Any]], tools: Optional[List[Any]] = None) -> Dict[str, Any]:
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

        # Extract system prompt if present
        system_prompt = ""
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                user_messages.append(msg)

        try:
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=config.LLM_MAX_TOKENS,
                system=system_prompt,
                messages=user_messages,
                tools=claude_tools
            )

            thought = ""
            for content in response.content:
                if content.type == "text":
                    thought += content.text

            if response.stop_reason == "tool_use":
                for content in response.content:
                    if content.type == "tool_use":
                        action_name = content.name
                        args = content.input
                        result = self._map_tool_response(action_name, args)
                        result["thought"] = thought
                        result["tool_call_id"] = content.id
                        return result

            return {"action": "IDLE", "thought": thought, "reason": "No tool called"}

        except Exception as e:
            logger.error(f"Anthropic API Error: {e}")
            return {"action": "IDLE", "reason": str(e)}

class GeminiLLM(LLMProvider):
    def __init__(self, api_key: str = None, model_name: str = "gemini-2.0-flash"):
        # Support multiple keys via comma-separated string
        keys_str = api_key or os.getenv("GEMINI_API_KEYS") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
        self.api_keys = [k.strip() for k in keys_str.split(',') if k.strip()]
        self.model_name = model_name
        self.action_models = ALL_ACTIONS
        self._setup_tools()
        self._max_retries = 3
        self._retry_delay = 5

    def _setup_tools(self):
        declarations = [pydantic_to_gemini_tool(m) for m in self.action_models]
        self.default_tools = [types.Tool(function_declarations=declarations)]

    def _get_client(self):
        if not self.api_keys:
            return None
        # Simple rotation or just pick first
        return genai.Client(api_key=self.api_keys[0])

    def generate_response(self, messages: List[Dict[str, Any]], tools: Optional[List[Any]] = None) -> Dict[str, Any]:
        client = self._get_client()
        if not client:
            return {"action": "IDLE", "reason": "Missing Gemini API Key"}

        active_tools = self.default_tools
        if tools:
            declarations = [pydantic_to_gemini_tool(m) for m in tools]
            active_tools = [types.Tool(function_declarations=declarations)]

        # Format messages for Gemini 2.0 SDK — convert structured
        # tool_calls/responses to text to avoid thought_signature requirements
        contents: list[types.Content] = []
        system_instruction = None

        def _append_or_merge(role: str, part) -> None:
            if contents and contents[-1].role == role:
                contents[-1].parts.append(part)
            else:
                contents.append(types.Content(role=role, parts=[part]))

        for msg in messages:
            role = msg["role"]
            content = msg.get("content")

            if role == "system":
                system_instruction = content
            elif role == "user":
                _append_or_merge("user", types.Part.from_text(text=content))
            elif role == "assistant":
                text = content or ""
                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        fn_name = tc["function"]["name"]
                        fn_args = tc["function"]["arguments"]
                        text += f"\nCall: {fn_name}({fn_args})"
                contents.append(types.Content(role="model", parts=[types.Part.from_text(text=text)]))
            elif role == "tool":
                text = f"[Result of {msg.get('tool_name', msg.get('function_name', 'tool'))}]: {content}"
                _append_or_merge("user", types.Part.from_text(text=text))

        import time as time_module

        try:
            for attempt in range(self._max_retries):
                try:
                    response = client.models.generate_content(
                        model=self.model_name,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            tools=active_tools
                        )
                    )
                    break
                except Exception as e:
                    err_str = str(e)
                    if attempt < self._max_retries - 1 and ("503" in err_str or "UNAVAILABLE" in err_str or "500" in err_str):
                        logger.warning(f"Gemini API transient error (attempt {attempt + 1}/{self._max_retries}): {e}")
                        time_module.sleep(self._retry_delay * (attempt + 1))
                        continue
                    raise

            if response.candidates and response.candidates[0].content.parts:
                thought = ""
                parts = response.candidates[0].content.parts
                for p in parts:
                    if p.text:
                        thought += p.text

                for p in parts:
                    if p.function_call:
                        fc = p.function_call
                        args = dict(fc.args)
                        result = self._map_tool_response(fc.name, args)
                        result["thought"] = thought
                        result["tool_call_id"] = "gemini_call"
                        return result

            return {"action": "IDLE", "thought": thought if 'thought' in locals() else "", "reason": "No tool called"}

        except Exception as e:
            logger.error(f"Gemini API Error: {e}")
            return {"action": "IDLE", "reason": str(e)}

class MockLLM(LLMProvider):
    def generate_response(self, messages: List[Dict[str, Any]], tools: Optional[List[Any]] = None) -> Dict[str, Any]:
        actions = [
            {"action": "CHAT", "message": "I am operating in MOCK MODE.", "thought": "I should let them know."},
            {"action": "MOVE", "target": "100 64 100", "thought": "Moving..."},
            {"action": "IDLE", "reason": "Simulated wait", "thought": "Waiting..."}
        ]
        return random.choice(actions)

def get_llm_provider(provider_name: str, **kwargs) -> LLMProvider:
    if os.getenv("MOCK_MODE", "").lower() == "true":
        logger.info("MOCK_MODE enabled. Forcing MockLLM.")
        return MockLLM()

    provider_name = provider_name.lower()

    if provider_name == "openai":
        return OpenAILLM(**kwargs)
    elif provider_name == "anthropic" or provider_name == "claude":
        return AnthropicLLM(**kwargs)
    elif provider_name == "gemini":
        # Check if we have a native Gemini key (env var or passed via kwargs)
        if (os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEYS") or os.getenv("GOOGLE_API_KEY")
                or kwargs.get("api_key")):
            return GeminiLLM(**kwargs)
        # Fallback to proxy
        if "base_url" not in kwargs:
            kwargs["base_url"] = os.getenv("OPENAI_BASE_URL", config.LLM_PROXY_URL) # Assume litellm proxy or similar
        return OpenAILLM(**kwargs)
    elif provider_name == "groq":
        kwargs.setdefault("base_url", "https://api.groq.com/openai/v1")
        kwargs.setdefault("model_name", "llama3-70b-8192")
        return OpenAILLM(**kwargs)
    elif provider_name in ["ollama", "gemma"]:
        kwargs.setdefault("base_url", "http://localhost:11434/v1")
        kwargs.setdefault("model_name", "llama3.1")
        return OpenAILLM(**kwargs)

    return MockLLM()
