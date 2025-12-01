from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Union

# --- Core Actions ---
class MoveAction(BaseModel):
    action: Literal["MOVE"] = "MOVE"
    target: str = Field(..., description="The name of the target entity, saved location, or block to move towards.")
    
class ChatAction(BaseModel):
    action: Literal["CHAT"] = "CHAT"
    message: str = Field(..., description="The message to say in chat.")

class MineAction(BaseModel):
    action: Literal["MINE"] = "MINE"
    block_name: str = Field(..., description="The name of the block to mine.")
    count: int = Field(1, description="Number of blocks to mine.")

class CraftAction(BaseModel):
    action: Literal["CRAFT"] = "CRAFT"
    item_name: str = Field(..., description="The name of the item to craft.")
    count: int = Field(1, description="Number of items to craft.")

class EquipAction(BaseModel):
    action: Literal["EQUIP"] = "EQUIP"
    item_name: str = Field(..., description="The name of the item to equip.")
    slot: Literal["hand", "head", "torso", "legs", "feet", "off-hand"] = "hand"

class IdleAction(BaseModel):
    action: Literal["IDLE"] = "IDLE"
    reason: str = Field(..., description="Reason for idling.")

# --- High Level Directives ---

class SetCombatMode(BaseModel):
    action: Literal["SET_COMBAT_MODE"] = "SET_COMBAT_MODE"
    mode: Literal["pvp", "none"] = Field(..., description="Enable or disable PvP mode.")
    target: Optional[str] = Field(None, description="The target entity name if mode is pvp.")

class SetSurvivalPreset(BaseModel):
    action: Literal["SET_SURVIVAL"] = "SET_SURVIVAL"
    preset: Literal["brave", "cowardly", "neutral"] = Field(..., description="Behavior preset regarding hostile mobs.")

class BuildStructure(BaseModel):
    action: Literal["BUILD"] = "BUILD"
    structure_type: Literal["wall", "floor"] = Field(..., description="Type of structure to build.")
    location: Optional[str] = Field(None, description="Target location 'x y z' or relative.")

class ManageInventory(BaseModel):
    action: Literal["INVENTORY"] = "INVENTORY"
    task: Literal["equip_best", "sort", "discard_junk"] = Field(..., description="Inventory management task.")

# --- Exploration & Memory ---

class SaveLocation(BaseModel):
    action: Literal["SAVE_LOCATION"] = "SAVE_LOCATION"
    name: str = Field(..., description="Name to assign to the current location.")

class SetExplorationMode(BaseModel):
    action: Literal["SET_EXPLORATION_MODE"] = "SET_EXPLORATION_MODE"
    mode: Literal["wander", "follow", "stop"] = Field(..., description="Exploration behavior.")
    target: Optional[str] = Field(None, description="Target entity to follow if mode is 'follow'.")

# --- Narrator Actions ---
class BroadcastEvent(BaseModel):
    action: Literal["BROADCAST"] = "BROADCAST"
    message: str = Field(..., description="The message to display to all players.")

class SpawnEvent(BaseModel):
    action: Literal["SPAWN"] = "SPAWN"
    entity_type: str = Field(..., description="The entity ID to spawn.")
    location: str = Field("random", description="'random' or coordinates 'x y z'")

class WeatherEvent(BaseModel):
    action: Literal["WEATHER"] = "WEATHER"
    type: Literal["clear", "rain", "thunder"] = "clear"

class WaitEvent(BaseModel):
    action: Literal["WAIT"] = "WAIT"
    reason: str = Field(..., description="Why the narrator is waiting.")

# Unions
AgentAction = Union[
    MoveAction, ChatAction, MineAction, CraftAction, EquipAction, IdleAction,
    SetCombatMode, SetSurvivalPreset, BuildStructure, ManageInventory,
    SaveLocation, SetExplorationMode
]

NarratorAction = Union[BroadcastEvent, SpawnEvent, WeatherEvent, WaitEvent]
