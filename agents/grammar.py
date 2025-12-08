from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Union

# --- Core Actions ---
class MoveAction(BaseModel):
    action: Literal["MOVE"] = "MOVE"
    target: str = Field(..., description="The name of the target entity, saved location, or block to move towards. Resolves 'Arrived' or 'NoPath'.")
    
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

class StopAction(BaseModel):
    action: Literal["STOP"] = "STOP"
    reason: str = Field(..., description="Reason for stopping current action.")

class InteractAction(BaseModel):
    action: Literal["INTERACT"] = "INTERACT"
    target_block: str = Field(..., description="Name of block to interact with (e.g. chest, door).")

# --- High Level Directives ---

class AttackAction(BaseModel):
    action: Literal["SET_COMBAT_MODE"] = "SET_COMBAT_MODE" 
    # Kept as SET_COMBAT_MODE for compatibility with existing prompt/logic if not fully renamed, 
    # but description emphasizes discrete attack.
    # Actually, let's keep the name mapping to 'SET_COMBAT_MODE' to match index.js for now,
    # or I need to update index.js to accept 'ATTACK'.
    # I'll stick to SET_COMBAT_MODE string for the JSON 'action' field to match index.js, 
    # but the class name is AttackAction.
    mode: Literal["pvp", "none"] = Field("pvp", description="Set to 'pvp' to attack.")
    target: Optional[str] = Field(None, description="Target to attack. Required if mode='pvp'. Action ends when target dies or bot retreats.")

class BuildStructure(BaseModel):
    action: Literal["BUILD"] = "BUILD"
    structure_type: Literal["wall", "floor", "shelter", "tower"] = Field(..., description="Type of structure to build.")
    location: Optional[str] = Field(None, description="Target location 'x y z' or relative.")

class BreakBlock(BaseModel):
    action: Literal["BREAK_BLOCK"] = "BREAK_BLOCK"
    block_name: Optional[str] = Field(None, description="Name of block to break. Required if no position is specified.")
    position: Optional[str] = Field(None, description="Coordinates 'x y z' to break. If omitted, searches for block_name.")

class PlaceBlock(BaseModel):
    action: Literal["PLACE_BLOCK"] = "PLACE_BLOCK"
    block_name: str = Field(..., description="Block to place.")
    position: Optional[str] = Field(None, description="Target coordinates 'x y z'.")
    near_block: Optional[str] = Field(None, description="Name of nearby block to place against (e.g. 'put torch on crafting_table').")

class InspectZone(BaseModel):
    action: Literal["INSPECT_ZONE"] = "INSPECT_ZONE"
    corner1: str = Field(..., description="Corner 1 coordinates. Max volume 512 blocks (e.g. 8x8x8).")
    corner2: str = Field(..., description="Corner 2 coordinates.")

class ThrowItem(BaseModel):
    action: Literal["THROW_ITEM"] = "THROW_ITEM"
    item_name: str = Field(..., description="Item to throw.")
    count: int = Field(1, description="Amount to throw.")

class UseItem(BaseModel):
    action: Literal["USE_ITEM"] = "USE_ITEM"
    item_name: str = Field(..., description="Item to use/consume.")

class MountEntity(BaseModel):
    action: Literal["MOUNT"] = "MOUNT"
    target: str = Field(..., description="Entity to mount.")

class DismountEntity(BaseModel):
    action: Literal["DISMOUNT"] = "DISMOUNT"
    reason: str = Field("None", description="Reason.")

class Sleep(BaseModel):
    action: Literal["SLEEP"] = "SLEEP"
    reason: str = Field("Night", description="Reason.")

class Wake(BaseModel):
    action: Literal["WAKE"] = "WAKE"
    reason: str = Field("Day", description="Reason.")

class ManageInventory(BaseModel):
    action: Literal["INVENTORY"] = "INVENTORY"
    task: Literal["equip_best", "sort", "discard_junk"] = Field(..., description="Inventory management task.")

# --- Exploration & Memory ---

class SaveLocation(BaseModel):
    action: Literal["SAVE_LOCATION"] = "SAVE_LOCATION"
    name: str = Field(..., description="Name to assign to the current location.")

class ExploreAction(BaseModel):
    action: Literal["SET_EXPLORATION_MODE"] = "SET_EXPLORATION_MODE"
    mode: Literal["wander", "follow", "stop"] = Field(..., description="'wander': move to random spot. 'follow': go to target.")
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
    MoveAction, ChatAction, MineAction, CraftAction, EquipAction, IdleAction, StopAction,
    AttackAction, BuildStructure, PlaceBlock, InspectZone, ManageInventory, InteractAction,
    BreakBlock, ThrowItem, UseItem, MountEntity, DismountEntity, Sleep, Wake,
    SaveLocation, ExploreAction
]

NarratorAction = Union[BroadcastEvent, SpawnEvent, WeatherEvent, WaitEvent]
