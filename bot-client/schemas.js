const { z } = require('zod');

const ChatSchema = z.object({
  action: z.literal('CHAT'),
  message: z.string(),
});

const MoveSchema = z.object({
  action: z.literal('MOVE'),
  target: z.string(),
});

const MineSchema = z.object({
  action: z.literal('MINE'),
  block_name: z.string(),
  count: z.number().optional().default(1),
});

const CraftSchema = z.object({
  action: z.literal('CRAFT'),
  item_name: z.string(),
  count: z.number().optional().default(1),
});

const EquipSchema = z.object({
  action: z.literal('EQUIP'),
  item_name: z.string(),
  slot: z.string().optional().default('hand'),
});

const IdleSchema = z.object({
  action: z.literal('IDLE'),
  reason: z.string().optional(),
});

const StopSchema = z.object({
  action: z.literal('STOP'),
  reason: z.string().optional(),
});

const InteractSchema = z.object({
  action: z.literal('INTERACT'),
  target_block: z.string(),
});

const GatherSchema = z.object({
  action: z.literal('GATHER'),
  resource: z.string(),
  count: z.number().optional().default(1),
});

const HuntSchema = z.object({
  action: z.literal('HUNT'),
  creature_name: z.string(),
  count: z.number().optional().default(1),
});

const CollectItemSchema = z.object({
  action: z.literal('COLLECT_ITEM'),
  item_name: z.string(),
  count: z.number().optional().default(1),
});

const SmeltSchema = z.object({
  action: z.literal('SMELT'),
  item_name: z.string(),
  fuel_name: z.string(),
  count: z.number().optional().default(1),
});

const ClearAreaSchema = z.object({
  action: z.literal('CLEAR_AREA'),
  corner1: z.string(),
  corner2: z.string(),
});

const DepositSchema = z.object({
  action: z.literal('DEPOSIT'),
  item_name: z.string().optional().default('all'),
  count: z.number().optional(),
});

const FarmSchema = z.object({
  action: z.literal('FARM'),
  mode: z.enum(['harvest', 'plant', 'cycle']).optional().default('cycle'),
  crop_name: z.string(),
  count: z.number().optional().default(10),
});

const SetCombatModeSchema = z.object({
  action: z.literal('SET_COMBAT_MODE'),
  mode: z.enum(['pvp', 'none']),
  target: z.string().optional(),
});

const BuildSchema = z.object({
  action: z.literal('BUILD'),
  shape: z.string(),
  material: z.string(),
  dimensions: z.string(),
  location: z.string().optional(),
});

const BreakBlockSchema = z.object({
  action: z.literal('BREAK_BLOCK'),
  block_name: z.string().optional(),
  position: z.string().optional(),
});

const PlaceBlockSchema = z.object({
  action: z.literal('PLACE_BLOCK'),
  block_name: z.string(),
  position: z.string().optional(),
  near_block: z.string().optional(),
});

const InspectZoneSchema = z.object({
  action: z.literal('INSPECT_ZONE'),
  corner1: z.string(),
  corner2: z.string(),
});

const ThrowItemSchema = z.object({
  action: z.literal('THROW_ITEM'),
  item_name: z.string(),
  count: z.number().optional().default(1),
});

const UseItemSchema = z.object({
  action: z.literal('USE_ITEM'),
  item_name: z.string(),
});

const MountSchema = z.object({
  action: z.literal('MOUNT'),
  target: z.string(),
});

const DismountSchema = z.object({
  action: z.literal('DISMOUNT'),
  reason: z.string().optional(),
});

const SleepSchema = z.object({
  action: z.literal('SLEEP'),
  reason: z.string().optional(),
});

const WakeSchema = z.object({
  action: z.literal('WAKE'),
  reason: z.string().optional(),
});

const InventorySchema = z.object({
  action: z.literal('INVENTORY'),
  task: z.enum(['equip_best', 'sort', 'discard_junk']),
});

const SaveLocationSchema = z.object({
  action: z.literal('SAVE_LOCATION'),
  name: z.string(),
});

const RememberSchema = z.object({
  action: z.literal('REMEMBER'),
  fact: z.string(),
});

const SetExplorationModeSchema = z.object({
  action: z.literal('SET_EXPLORATION_MODE'),
  mode: z.enum(['wander', 'follow', 'stop', 'map', 'find_biome']),
  target: z.string().optional(),
});

const ConfigureSchema = z.object({
  action: z.literal('CONFIGURE'),
  mode: z.string(),
  setting: z.string(),
});

const ActionSchemas = {
  CHAT: ChatSchema,
  MOVE: MoveSchema,
  MINE: MineSchema,
  CRAFT: CraftSchema,
  EQUIP: EquipSchema,
  IDLE: IdleSchema,
  STOP: StopSchema,
  INTERACT: InteractSchema,
  GATHER: GatherSchema,
  HUNT: HuntSchema,
  COLLECT_ITEM: CollectItemSchema,
  SMELT: SmeltSchema,
  CLEAR_AREA: ClearAreaSchema,
  DEPOSIT: DepositSchema,
  FARM: FarmSchema,
  SET_COMBAT_MODE: SetCombatModeSchema,
  BUILD: BuildSchema,
  BREAK_BLOCK: BreakBlockSchema,
  PLACE_BLOCK: PlaceBlockSchema,
  INSPECT_ZONE: InspectZoneSchema,
  THROW_ITEM: ThrowItemSchema,
  USE_ITEM: UseItemSchema,
  MOUNT: MountSchema,
  DISMOUNT: DismountSchema,
  SLEEP: SleepSchema,
  WAKE: WakeSchema,
  INVENTORY: InventorySchema,
  SAVE_LOCATION: SaveLocationSchema,
  REMEMBER: RememberSchema,
  SET_EXPLORATION_MODE: SetExplorationModeSchema,
  CONFIGURE: ConfigureSchema,
};

const CommandSchema = z.discriminatedUnion('action', [
  ChatSchema, MoveSchema, MineSchema, CraftSchema, EquipSchema,
  IdleSchema, StopSchema, InteractSchema, GatherSchema, HuntSchema,
  CollectItemSchema, SmeltSchema, ClearAreaSchema, DepositSchema, FarmSchema,
  SetCombatModeSchema, BuildSchema, BreakBlockSchema, PlaceBlockSchema,
  InspectZoneSchema, ThrowItemSchema, UseItemSchema, MountSchema, DismountSchema,
  SleepSchema, WakeSchema, InventorySchema, SaveLocationSchema, RememberSchema,
  SetExplorationModeSchema, ConfigureSchema,
]);

function validateCommand(data) {
  return CommandSchema.safeParse(data);
}

module.exports = { validateCommand, ActionSchemas };
