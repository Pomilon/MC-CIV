from typing import Literal, Optional, Union

from pydantic import BaseModel, Field


# --- Core Actions ---
class MOVE(BaseModel):
    action: Literal["MOVE"] = "MOVE"
    target: str = Field(..., description="The name of the target entity, saved location, or block to move towards. Resolves 'Arrived' or 'NoPath'.")

class CHAT(BaseModel):
    action: Literal["CHAT"] = "CHAT"
    message: str = Field(..., description="The message to say in chat.")

class MINE(BaseModel):
    action: Literal["MINE"] = "MINE"
    block_name: str = Field(..., description="The name of the block to mine.")
    count: int = Field(1, description="Number of blocks to mine.")

class CRAFT(BaseModel):
    action: Literal["CRAFT"] = "CRAFT"
    item_name: str = Field(..., description="The name of the item to craft.")
    count: int = Field(1, description="Number of items to craft.")

class EQUIP(BaseModel):
    action: Literal["EQUIP"] = "EQUIP"
    item_name: str = Field(..., description="The name of the item to equip.")
    slot: Literal["hand", "head", "torso", "legs", "feet", "off-hand"] = "hand"

class IDLE(BaseModel):
    action: Literal["IDLE"] = "IDLE"
    reason: str = Field(..., description="Reason for idling.")

class STOP(BaseModel):
    action: Literal["STOP"] = "STOP"
    reason: str = Field(..., description="Reason for stopping current action.")

class INTERACT(BaseModel):
    action: Literal["INTERACT"] = "INTERACT"
    target_block: str = Field(..., description="Name of block to interact with (e.g. chest, door).")

class GATHER(BaseModel):
    action: Literal["GATHER"] = "GATHER"
    resource: str = Field(..., description="Name of the block/resource to gather (e.g., 'oak_log', 'cobblestone').")
    count: int = Field(1, description="Number of items/blocks to collect. The bot will search and mine until this amount is reached.")

class HUNT(BaseModel):
    action: Literal["HUNT"] = "HUNT"
    creature_name: str = Field(..., description="Name of the creature to hunt (e.g., 'pig', 'zombie').")
    count: int = Field(1, description="Number of creatures to defeat.")

class COLLECT_ITEM(BaseModel):
    action: Literal["COLLECT_ITEM"] = "COLLECT_ITEM"
    item_name: str = Field(..., description="Name of the dropped item to search for and pick up.")
    count: int = Field(1, description="Number of items to collect.")

class SMELT(BaseModel):
    action: Literal["SMELT"] = "SMELT"
    item_name: str = Field(..., description="Item to smelt (e.g. 'raw_iron').")
    fuel_name: str = Field(..., description="Fuel to use (e.g. 'coal').")
    count: int = Field(1, description="Number of items to smelt.")

class CLEAR_AREA(BaseModel):
    action: Literal["CLEAR_AREA"] = "CLEAR_AREA"
    corner1: str = Field(..., description="Corner 1 coordinates.")
    corner2: str = Field(..., description="Corner 2 coordinates.")

class DEPOSIT(BaseModel):
    action: Literal["DEPOSIT"] = "DEPOSIT"
    item_name: str = Field("all", description="Item to deposit, or 'all'.")
    count: Optional[int] = Field(None, description="Amount to deposit. If None, deposits all.")

class FARM(BaseModel):
    action: Literal["FARM"] = "FARM"
    mode: Literal["harvest", "plant", "cycle"] = Field("cycle", description="'cycle' means harvest mature crops and replant.")
    crop_name: str = Field(..., description="Crop to farm (e.g. 'wheat', 'carrots').")
    count: int = Field(10, description="Approximate number of blocks to process.")

# --- High Level Directives ---

class SET_COMBAT_MODE(BaseModel):
    action: Literal["SET_COMBAT_MODE"] = "SET_COMBAT_MODE"
    mode: Literal["pvp", "none"] = Field("pvp", description="Set to 'pvp' to attack.")
    target: Optional[str] = Field(None, description="Target to attack. Required if mode='pvp'. Action ends when target dies or bot retreats.")

class BUILD(BaseModel):
    action: Literal["BUILD"] = "BUILD"
    shape: Literal["wall", "floor", "box", "hollow_box", "tower", "stairs", "pyramid"] = Field(..., description="Geometric shape to build.")
    material: str = Field(..., description="Block name to use (e.g. 'cobblestone').")
    dimensions: str = Field(..., description="Size 'width height depth' (e.g. '10 5 10').")
    location: Optional[str] = Field(None, description="Bottom-south-west corner 'x y z'.")

class BREAK_BLOCK(BaseModel):
    action: Literal["BREAK_BLOCK"] = "BREAK_BLOCK"
    block_name: Optional[str] = Field(None, description="Name of block to break. Required if no position is specified.")
    position: Optional[str] = Field(None, description="Coordinates 'x y z' to break. If omitted, searches for block_name.")

class PLACE_BLOCK(BaseModel):
    action: Literal["PLACE_BLOCK"] = "PLACE_BLOCK"
    block_name: str = Field(..., description="Block to place.")
    position: Optional[str] = Field(None, description="Target coordinates 'x y z'.")
    near_block: Optional[str] = Field(None, description="Name of nearby block to place against (e.g. 'put torch on crafting_table').")

class INSPECT_ZONE(BaseModel):
    action: Literal["INSPECT_ZONE"] = "INSPECT_ZONE"
    corner1: str = Field(..., description="Corner 1 coordinates. Max volume 512 blocks (e.g. 8x8x8).")
    corner2: str = Field(..., description="Corner 2 coordinates.")

class THROW_ITEM(BaseModel):
    action: Literal["THROW_ITEM"] = "THROW_ITEM"
    item_name: str = Field(..., description="Item to throw.")
    count: int = Field(1, description="Amount to throw.")

class USE_ITEM(BaseModel):
    action: Literal["USE_ITEM"] = "USE_ITEM"
    item_name: str = Field(..., description="Item to use/consume.")

class MOUNT(BaseModel):
    action: Literal["MOUNT"] = "MOUNT"
    target: str = Field(..., description="Entity to mount.")

class DISMOUNT(BaseModel):
    action: Literal["DISMOUNT"] = "DISMOUNT"
    reason: str = Field("None", description="Reason.")

class SLEEP(BaseModel):
    action: Literal["SLEEP"] = "SLEEP"
    reason: str = Field("Night", description="Reason.")

class WAKE(BaseModel):
    action: Literal["WAKE"] = "WAKE"
    reason: str = Field("Day", description="Reason.")

class INVENTORY(BaseModel):
    action: Literal["INVENTORY"] = "INVENTORY"
    task: Literal["equip_best", "sort", "discard_junk"] = Field(..., description="Inventory management task.")

# --- Trading, Enchanting, Repair ---

class TRADE(BaseModel):
    action: Literal["TRADE"] = "TRADE"
    target: str = Field(..., description="Name of the villager or wandering trader to trade with.")
    choice_index: int = Field(0, description="Which trade to select (0-based index). The bot opens the trade UI and executes the chosen trade.")
    count: int = Field(1, description="How many times to perform the trade.")

class ENCHANT(BaseModel):
    action: Literal["ENCHANT"] = "ENCHANT"
    item_name: str = Field(..., description="Item to enchant (must be in inventory, e.g. 'diamond_sword', 'bow').")
    choice: Literal["0", "1", "2"] = Field("0", description="Which enchantment slot to pick ('0', '1', '2'). Higher levels cost more XP.")

class REPAIR(BaseModel):
    action: Literal["REPAIR"] = "REPAIR"
    item_name: str = Field(..., description="Item to repair, rename, or disenchant.")
    mode: Literal["repair", "rename", "disenchant"] = Field("repair", description="'repair' fixes durability with materials (anvil). 'rename' renames an item (anvil). 'disenchant' removes enchantments for XP (grindstone).")
    new_name: Optional[str] = Field(None, description="New name for the item if mode='rename'.")

class WITHDRAW(BaseModel):
    action: Literal["WITHDRAW"] = "WITHDRAW"
    item_name: str = Field(..., description="Item to take from a container (e.g. 'iron_ingot', 'diamond').")
    count: int = Field(1, description="Number of items to withdraw.")
    container: Optional[str] = Field(None, description="Block type of container (e.g. 'chest', 'barrel', 'shulker_box'). Uses the nearest matching container if omitted.")

class USE_ON(BaseModel):
    action: Literal["USE_ON"] = "USE_ON"
    item_name: str = Field(..., description="Item to use on the target (e.g. 'shears' to shear sheep, 'bucket' to milk cow, 'bone_meal' to fertilize crops, 'wheat' to breed cows/sheep, 'lead' to leash, 'name_tag' to name, 'saddle' to equip mount, 'flint_and_steel' to ignite, 'brush' to brush, 'glass_bottle' to collect honey/water, 'honeycomb' to wax copper).")
    target_block: Optional[str] = Field(None, description="Target block type (e.g. 'wheat' to bonemeal, 'suspicious_sand' to brush).")
    target_entity: Optional[str] = Field(None, description="Target entity type (e.g. 'sheep' to shear, 'cow' to milk, 'wolf' to tame/breed, 'horse' to saddle or feed).")
    entity_name: Optional[str] = Field(None, description="Custom name to apply if using a name tag.")

class FISH(BaseModel):
    action: Literal["FISH"] = "FISH"
    reason: str = Field("Fishing", description="Reason for fishing.")

# --- Exploration & Memory ---

class SAVE_LOCATION(BaseModel):
    action: Literal["SAVE_LOCATION"] = "SAVE_LOCATION"
    name: str = Field(..., description="Name to assign to the current location.")

class REMEMBER(BaseModel):
    action: Literal["REMEMBER"] = "REMEMBER"
    fact: str = Field(..., description="A fact or piece of information to store in long-term memory.")

class SET_EXPLORATION_MODE(BaseModel):
    action: Literal["SET_EXPLORATION_MODE"] = "SET_EXPLORATION_MODE"
    mode: Literal["wander", "follow", "stop", "map", "find_biome"] = Field(..., description="'wander': random move. 'map': systematic spiral search of unvisited chunks. 'find_biome': search for biome. 'follow': follow entity.")
    target: Optional[str] = Field(None, description="Target entity for 'follow' or biome name for 'find_biome'.")

class CONFIGURE(BaseModel):
    action: Literal["CONFIGURE"] = "CONFIGURE"
    mode: Literal["self_defense", "auto_eat", "auto_sleep", "auto_collect",
                  "low_health_threshold", "low_health_action", "on_totem_pop", "auto_tool_swap"] = Field(..., description="Behavior to configure.")
    setting: str = Field(..., description="Setting value (e.g. 'fight', 'flee', 'true', '5', 'run_away').")

# --- Narrator Actions ---
class BROADCAST(BaseModel):
    action: Literal["BROADCAST"] = "BROADCAST"
    message: str = Field(..., description="The message to display to all players.")

class SPAWN(BaseModel):
    action: Literal["SPAWN"] = "SPAWN"
    entity_type: str = Field(..., description="The entity ID to spawn.")
    location: str = Field("random", description="'random' or coordinates 'x y z'")

class WEATHER(BaseModel):
    action: Literal["WEATHER"] = "WEATHER"
    type: Literal["clear", "rain", "thunder"] = "clear"

class WAIT(BaseModel):
    action: Literal["WAIT"] = "WAIT"
    reason: str = Field(..., description="Why the narrator is waiting.")

# Unions
AgentAction = Union[
    MOVE, CHAT, MINE, GATHER, CRAFT, EQUIP, IDLE, STOP,
    SET_COMBAT_MODE, HUNT, BUILD, PLACE_BLOCK, INSPECT_ZONE, INVENTORY, INTERACT,
    BREAK_BLOCK, THROW_ITEM, USE_ITEM, COLLECT_ITEM, MOUNT, DISMOUNT, SLEEP, WAKE,
    SMELT, CLEAR_AREA, DEPOSIT, FARM, CONFIGURE,
    SAVE_LOCATION, REMEMBER, SET_EXPLORATION_MODE,
    TRADE, ENCHANT, REPAIR, WITHDRAW, USE_ON, FISH,
]

NarratorAction = Union[BROADCAST, SPAWN, WEATHER, WAIT]
