from pydantic import BaseModel, Field

from agents.memory import MemoryManager
from agents.tools.registry import Tool


class RECALL(BaseModel):
    query: str = Field(..., description="Query to search long-term memory.")


class REMEMBER(BaseModel):
    fact: str = Field(..., description="A fact or piece of information to store in long-term memory.")


class SAVE_LOCATION(BaseModel):
    name: str = Field(..., description="Name to assign to the current location.")


class SET_GOAL(BaseModel):
    goal: str = Field(..., description="A sub-goal to set for the agent.")


class REFLECT(BaseModel):
    topic: str = Field("recent events", description="Topic to reflect on.")


class FORGET(BaseModel):
    topic: str = Field(..., description="Topic to remove from long-term memory.")


def build_cognitive_tools(memory: MemoryManager) -> list[Tool]:
    return [
        Tool(
            name="RECALL",
            description="Search semantic memory for facts matching a query",
            schema=RECALL,
            handler=_make_recall(memory),
            category="cognitive",
        ),
        Tool(
            name="REMEMBER",
            description="Store a fact in semantic memory",
            schema=REMEMBER,
            handler=_make_remember(memory),
            category="cognitive",
        ),
        Tool(
            name="SAVE_LOCATION",
            description="Save current location with a name label",
            schema=SAVE_LOCATION,
            handler=_make_save_location(memory),
            category="cognitive",
            requires_body=True,
        ),
        Tool(
            name="SET_GOAL",
            description="Set or update the agent's current sub-goal",
            schema=SET_GOAL,
            handler=_make_set_goal(),
            category="cognitive",
        ),
        Tool(
            name="REFLECT",
            description="Summarize recent episodic events into insights, storing them as semantic facts",
            schema=REFLECT,
            handler=_make_reflect(),
            category="cognitive",
        ),
        Tool(
            name="FORGET",
            description="Remove facts matching a topic from semantic memory",
            schema=FORGET,
            handler=_make_forget(memory),
            category="cognitive",
        ),
    ]


def _make_recall(memory: MemoryManager):
    async def handler(query: str) -> str:
        results = memory.semantic.retrieve(query, top_k=5)
        if not results:
            return "No relevant memories found."
        lines = [f"- {k}: {v} (relevance: {s:.2f})" for k, v, s in results]
        return "Semantic Memory:\n" + "\n".join(lines)
    return handler


def _make_remember(memory: MemoryManager):
    async def handler(fact: str) -> str:
        key = fact.lower().replace(" ", "_")[:60]
        memory.add_fact(key, fact)
        return f"Stored: {fact}"
    return handler


def _make_save_location(memory: MemoryManager):
    async def handler(name: str) -> str:
        memory.add_fact(f"location:{name}", name)
        memory.add_event(f"Saved location: {name}", importance=3.0, tags=["location"])
        return f"Location saved as '{name}'"
    return handler


def _make_set_goal():
    _goal: str | None = None

    async def handler(goal: str) -> str:
        nonlocal _goal
        _goal = goal
        return f"Goal set: {goal}"
    return handler


def _make_reflect():
    async def handler(topic: str) -> str:
        return f"Reflection on '{topic}' would synthesize episodic events into insights."
    return handler


def _make_forget(memory: MemoryManager):
    async def handler(topic: str) -> str:
        count = 0
        for key in list(memory.semantic.facts.keys()):
            if topic.lower() in key.lower():
                memory.semantic.forget(key)
                count += 1
        return f"Forgot {count} facts about '{topic}'"
    return handler
