import logging
from dataclasses import dataclass
from typing import Any, Callable, Literal

from pydantic import BaseModel

logger = logging.getLogger(__name__)


@dataclass
class Tool:
    name: str
    description: str
    schema: type[BaseModel]
    handler: Callable[..., Any]
    category: Literal["body", "cognitive"]
    requires_body: bool = False
    timeout: float = 30.0


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def declarations(self) -> list[type[BaseModel]]:
        return [t.schema for t in self._tools.values()]

    def has(self, name: str) -> bool:
        return name in self._tools

    async def execute(self, name: str, args: dict) -> Any:
        tool = self._tools.get(name)
        if not tool:
            raise ValueError(f"Unknown tool: {name}")

        try:
            clean_args = tool.schema(**args).model_dump()
        except Exception:
            clean_args = {k: v for k, v in args.items() if k not in ("action", "thought", "tool_call_id")}

        logger.info(f"Executing tool {name} with args={clean_args}")
        try:
            result = await tool.handler(**clean_args)
            return result
        except Exception as e:
            logger.error(f"Tool {name} failed: {e}")
            return {"status": "error", "error": str(e)}

    @property
    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def __len__(self) -> int:
        return len(self._tools)
