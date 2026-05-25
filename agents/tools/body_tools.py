import logging
from collections.abc import Callable

from pydantic import BaseModel

from agents import grammar
from agents.tools.registry import Tool

logger = logging.getLogger(__name__)

_NARRATOR_ACTIONS = {"BROADCAST", "SPAWN", "WEATHER", "WAIT"}

_AGENT_ACTION_CLASSES: dict[str, type[BaseModel]] = {}
for name in dir(grammar):
    if name.startswith("_"):
        continue
    cls = getattr(grammar, name, None)
    if (
        isinstance(cls, type)
        and issubclass(cls, BaseModel)
        and cls is not BaseModel
        and "action" in cls.model_fields
    ):
        _AGENT_ACTION_CLASSES[name] = cls

_COGNITIVE_EXCLUDED = {"SAVE_LOCATION", "REMEMBER"}

_TOOL_DESCRIPTIONS: dict[str, str] = {
    "MOVE": "Move the bot to a target entity or location.",
    "CHAT": "Send a chat message.",
    "MINE": "Mine a specific block type.",
    "GATHER": "Gather resources by searching and mining (waits until target count reached).",
    "CRAFT": "Craft an item from available materials.",
    "EQUIP": "Equip an item to a specific equipment slot.",
    "INTERACT": "Interact with a block (chest, door, lever, etc.).",
    "HUNT": "Hunt and defeat hostile or passive creatures.",
    "COLLECT_ITEM": "Search for and pick up dropped items on the ground.",
    "SMELT": "Smelt an item in a furnace using specified fuel.",
    "CLEAR_AREA": "Clear all blocks between two corner coordinates.",
    "DEPOSIT": "Deposit items into a nearby container (chest, barrel).",
    "FARM": "Harvest, plant, or cycle crops in a farm.",
    "SET_COMBAT_MODE": "Set the bot's combat behavior (PvP mode or none).",
    "BUILD": "Build a geometric structure (wall, floor, box, tower, etc.).",
    "BREAK_BLOCK": "Break a specific block by name or at coordinates.",
    "PLACE_BLOCK": "Place a block at a position or near another block.",
    "INSPECT_ZONE": "Scan blocks in a volume between two corners.",
    "THROW_ITEM": "Throw or drop an item from inventory.",
    "USE_ITEM": "Use or consume an item (eat food, drink potion).",
    "MOUNT": "Mount a rideable entity (horse, boat, etc.).",
    "DISMOUNT": "Dismount from a currently mounted entity.",
    "SLEEP": "Sleep in a nearby bed.",
    "WAKE": "Wake up from sleeping.",
    "SET_EXPLORATION_MODE": "Set exploration behavior (wander, follow, map, find_biome).",
    "TRADE": "Trade with a villager or wandering trader (open trade UI, select a trade slot, execute the trade).",
    "ENCHANT": "Enchant an item at an enchanting table using lapis lazuli (put item, select enchantment slot 0-2, take enchanted item).",
    "REPAIR": "Repair, rename, or disenchant items at an anvil or grindstone (repair fixed durability, rename changes the name, disenchant removes enchantments for XP).",
    "WITHDRAW": "Take items from a nearby container (chest, barrel, shulker box, etc.). The bot opens the container and removes the requested items.",
    "USE_ON": "Use a held item on a block or entity (shear sheep, milk cow, bone meal crops, flint & steel to ignite, brush suspicious blocks, dye sheep/wool, leash entities, name tag, saddle mount, collect honey with bottle, wax copper with honeycomb, tame/breed animals by feeding).",
    "FISH": "Fish with a fishing rod. Casts the line and waits for a catch.",
    "CONFIGURE": "Configure bot settings (auto-eat, auto-sleep, self-defense, etc.).",
    "IDLE": "Wait without performing any action, with a reason.",
    "STOP": "Stop the current action with a reason.",
    "INVENTORY": "Manage inventory (equip best, sort, discard junk).",
}


def build_body_tools(send_command: Callable) -> list[Tool]:
    tools: list[Tool] = []
    for name, cls in _AGENT_ACTION_CLASSES.items():
        if name in _COGNITIVE_EXCLUDED or name in _NARRATOR_ACTIONS:
            continue
        desc = _TOOL_DESCRIPTIONS.get(name, f"Execute the {name} action.")
        tool = Tool(
            name=name,
            description=desc,
            schema=cls,
            handler=_make_body_handler(name, send_command),
            category="body",
            requires_body=True,
        )
        tools.append(tool)
    return tools


def _make_body_handler(action: str, send_command: Callable):
    async def handler(**kwargs) -> str:
        return await send_command({"action": action, "params": kwargs})
    return handler
