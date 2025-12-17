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

class GatherResource(BaseModel):
    action: Literal["GATHER"] = "GATHER"
    resource: str = Field(..., description="Name of the block/resource to gather (e.g., 'oak_log', 'cobblestone').")
    count: int = Field(1, description="Number of items/blocks to collect. The bot will search and mine until this amount is reached.")

class HuntCreature(BaseModel):
    action: Literal["HUNT"] = "HUNT"
    creature_name: str = Field(..., description="Name of the creature to hunt (e.g., 'pig', 'zombie').")
    count: int = Field(1, description="Number of creatures to defeat.")

class FindAndCollect(BaseModel):
    action: Literal["COLLECT_ITEM"] = "COLLECT_ITEM"
    item_name: str = Field(..., description="Name of the dropped item to search for and pick up.")
    count: int = Field(1, description="Number of items to collect.")

class SmeltItem(BaseModel):
    action: Literal["SMELT"] = "SMELT"
    item_name: str = Field(..., description="Item to smelt (e.g. 'raw_iron').")
    fuel_name: str = Field(..., description="Fuel to use (e.g. 'coal').")
    count: int = Field(1, description="Number of items to smelt.")

class ClearArea(BaseModel):
    action: Literal["CLEAR_AREA"] = "CLEAR_AREA"
    corner1: str = Field(..., description="Corner 1 coordinates.")
    corner2: str = Field(..., description="Corner 2 coordinates.")

class DepositToChest(BaseModel):
    action: Literal["DEPOSIT"] = "DEPOSIT"
    item_name: str = Field("all", description="Item to deposit, or 'all'.")
    count: Optional[int] = Field(None, description="Amount to deposit. If None, deposits all.")

class FarmLoop(BaseModel):
    action: Literal["FARM"] = "FARM"
    mode: Literal["harvest", "plant", "cycle"] = Field("cycle", description="'cycle' means harvest mature crops and replant.")
    crop_name: str = Field(..., description="Crop to farm (e.g. 'wheat', 'carrots').")
    count: int = Field(10, description="Approximate number of blocks to process.")

# --- High Level Directives ---

class AttackAction(BaseModel):
    action: Literal["SET_COMBAT_MODE"] = "SET_COMBAT_MODE" 
    mode: Literal["pvp", "none"] = Field("pvp", description="Set to 'pvp' to attack.")
    target: Optional[str] = Field(None, description="Target to attack. Required if mode='pvp'. Action ends when target dies or bot retreats.")

class BuildStructure(BaseModel):
    action: Literal["BUILD"] = "BUILD"
    shape: Literal["wall", "floor", "box", "hollow_box", "tower", "stairs", "pyramid"] = Field(..., description="Geometric shape to build.")
    material: str = Field(..., description="Block name to use (e.g. 'cobblestone').")
    dimensions: str = Field(..., description="Size 'width height depth' (e.g. '10 5 10').")
    location: Optional[str] = Field(None, description="Bottom-south-west corner 'x y z'.")

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

class Remember(BaseModel):
    action: Literal["REMEMBER"] = "REMEMBER"
    fact: str = Field(..., description="A fact or piece of information to store in long-term memory.")

class ExploreAction(BaseModel):
    action: Literal["SET_EXPLORATION_MODE"] = "SET_EXPLORATION_MODE"
    mode: Literal["wander", "follow", "stop", "map", "find_biome"] = Field(..., description="'wander': random move. 'map': systematic spiral search of unvisited chunks. 'find_biome': search for biome. 'follow': follow entity.")
    target: Optional[str] = Field(None, description="Target entity for 'follow' or biome name for 'find_biome'.")

class ConfigureBehavior(BaseModel):
    action: Literal["CONFIGURE"] = "CONFIGURE"
    mode: Literal["self_defense", "auto_eat", "auto_sleep", "auto_collect", 
                  "low_health_threshold", "low_health_action", "on_totem_pop", "auto_tool_swap"] = Field(..., description="Behavior to configure.")
    setting: str = Field(..., description="Setting value (e.g. 'fight', 'flee', 'true', '5', 'run_away').")

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
    MoveAction, ChatAction, MineAction, GatherResource, CraftAction, EquipAction, IdleAction, StopAction,
    AttackAction, HuntCreature, BuildStructure, PlaceBlock, InspectZone, ManageInventory, InteractAction,
    BreakBlock, ThrowItem, UseItem, FindAndCollect, MountEntity, DismountEntity, Sleep, Wake,
    SmeltItem, ClearArea, DepositToChest, FarmLoop, ConfigureBehavior,
    SaveLocation, Remember, ExploreAction
]

NarratorAction = Union[BroadcastEvent, SpawnEvent, WeatherEvent, WaitEvent]
