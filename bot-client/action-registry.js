const Vec3 = require('vec3');
const { goals, Movements } = require('mineflayer-pathfinder');
const { getBlockByName, behaviors } = require('./bot-lifecycle');
const { setupMovements } = require('./pathfinder');

function withTimeout(promise, ms, label = 'Operation') {
  promise.catch(() => {});
  return Promise.race([
    promise,
    new Promise((_, reject) => setTimeout(() => reject(new Error(`${label} Timed Out after ${ms}ms`)), ms)),
  ]);
}

async function executeMove(bot, params) {
  const target = params.target;
  const defaultMove = setupMovements(bot);
  bot.pathfinder.setMovements(defaultMove);

  let goal = null;
  const coords = target.match(/(-?\d+)\s+(-?\d+)\s+(-?\d+)/);

  if (coords) {
    goal = new goals.GoalNear(parseInt(coords[1]), parseInt(coords[2]), parseInt(coords[3]), 1);
  } else {
    const player = bot.players[target];
    if (player && player.entity) {
      goal = new goals.GoalNear(player.entity.position.x, player.entity.position.y, player.entity.position.z, 1);
    } else {
      const block = getBlockByName(target);
      if (block) {
        goal = new goals.GoalNear(block.position.x, block.position.y, block.position.z, 1);
      }
    }
  }

  if (!goal) throw new Error('Target not found');

  return new Promise((resolve, reject) => {
    bot.pathfinder.setGoal(goal);
    let stuckCount = 0;

    const cleanup = () => {
      bot.removeListener('goal_reached', onGoalReached);
      bot.removeListener('path_update', onPathUpdate);
      bot.removeListener('stuck', onStuck);
    };

    const onGoalReached = () => {
      cleanup();
      resolve('Arrived');
    };

    const onPathUpdate = (r) => {
      if (r.status === 'noPath') {
        cleanup();
        reject(new Error('No Path Found'));
      }
    };

    const onStuck = async () => {
      stuckCount++;
      console.log(`[Move] Bot stuck! Attempt ${stuckCount}/3`);
      if (stuckCount > 3) {
        cleanup();
        reject(new Error('Bot stuck and cannot free itself'));
        return;
      }
      bot.pathfinder.stop();
      bot.setControlState('jump', true);
      bot.setControlState('forward', true);
      if (Math.random() > 0.5) bot.setControlState('left', true);
      else bot.setControlState('right', true);

      setTimeout(() => {
        bot.clearControlStates();
        bot.pathfinder.setGoal(goal);
      }, 1000);
    };

    bot.on('goal_reached', onGoalReached);
    bot.on('path_update', onPathUpdate);
    bot.on('stuck', onStuck);
  });
}

async function executeMine(bot, params) {
  const block = getBlockByName(params.block_name);
  if (!block) throw new Error('Block not found');

  bot.pathfinder.stop();
  await new Promise(r => setTimeout(r, 50));

  const defaultMove = setupMovements(bot);
  bot.pathfinder.setMovements(defaultMove);

  try {
    await bot.collectBlock.collect(block);
    return 'BlockMined';
  } catch (err) {
    throw new Error(err && err.message ? err.message : String(err));
  }
}

async function executeCraft(bot, params) {
  const ITEM_ALIASES = {
    'planks': 'oak_planks',
    'plank': 'oak_planks',
    'wooden_planks': 'oak_planks',
    'stick': 'stick',
    'pickaxe': 'wooden_pickaxe',
    'wood_pickaxe': 'wooden_pickaxe',
    'axe': 'wooden_axe',
    'sword': 'wooden_sword',
    'hoe': 'wooden_hoe',
    'door': 'oak_door',
    'wooden_door': 'oak_door',
    'stairs': 'oak_stairs',
    'fence': 'oak_fence',
    'gate': 'oak_fence_gate',
    'trapdoor': 'oak_trapdoor',
    'button': 'oak_button',
    'pressure_plate': 'oak_pressure_plate',
    'sign': 'oak_sign',
    'boat': 'oak_boat',
    'sapling': 'oak_sapling',
    'log': 'oak_log',
    'wood': 'oak_wood',
    'leaves': 'oak_leaves',
    'slab': 'oak_slab',
  };
  let itemName = params.item_name;
  if (ITEM_ALIASES[itemName]) itemName = ITEM_ALIASES[itemName];

  const count = params.count || 1;
  const item = bot.registry.itemsByName[itemName];
  if (!item) throw new Error(`Unknown item: ${itemName}`);
  const recipes = bot.recipesFor(item.id, null, 1, null);
  if (!recipes || recipes.length === 0) {
    const have = bot.inventory.items().map(i => `${i.name} (${i.count})`).join(', ');
    throw new Error(`Cannot craft ${itemName}. Inventory: ${have || 'empty'}. You may need to gather more resources or place a crafting table first.`);
  }
  const recipe = recipes[0];

  const qty = Math.floor(count);
  try {
    await withTimeout(bot.craft(recipe, qty, null), 15000 + (count * 200), 'Craft');
    return `Crafted_${qty}_${itemName}`;
  } catch (err) {
    throw new Error(err && err.message ? err.message : String(err));
  }
}

async function executeEquip(bot, params) {
  const itemToEquip = bot.inventory.items().find(i => i.name === params.item_name);
  if (!itemToEquip) throw new Error('ItemNotInInventory');
  await bot.equip(itemToEquip, params.slot || 'hand');
  return 'Equipped';
}

async function executeInteract(bot, params) {
  const block = getBlockByName(params.target_block);
  if (!block) throw new Error('BlockNotFound');
  await bot.activateBlock(block);
  return 'Interacted';
}

async function executeSetCombatMode(bot, params) {
  if (params.mode === 'pvp') {
    if (!params.target) throw new Error('TargetRequiredForPvP');
    return await behaviors.combat.engageTarget(bot, params.target);
  } else {
    if (bot.pvp) bot.pvp.stop();
    return 'CombatStopped';
  }
}

async function executeSetExplorationMode(bot, params) {
  if (params.mode === 'wander') {
    return await behaviors.exploration.wander(bot);
  } else if (params.mode === 'map') {
    return await behaviors.exploration.exploreMap(bot);
  } else if (params.mode === 'find_biome') {
    if (!params.target) throw new Error('Target biome required');
    return await behaviors.exploration.findBiome(bot, params.target);
  } else if (params.mode === 'follow') {
    if (!params.target) throw new Error('TargetRequiredForFollow');
    return await behaviors.exploration.follow(bot, params.target);
  } else if (params.mode === 'stop') {
    return 'ExplorationStopped';
  } else {
    throw new Error('Unknown exploration mode');
  }
}

async function executeBreakBlock(bot, params) {
  let breakPos = null;
  if (params.position) {
    const bCoords = params.position.match(/(-?\d+)\s+(-?\d+)\s+(-?\d+)/);
    if (bCoords) {
      breakPos = new Vec3(parseInt(bCoords[1]), parseInt(bCoords[2]), parseInt(bCoords[3]));
    }
  }
  return await behaviors.survival.breakBlock(bot, params.block_name, breakPos);
}

const registry = {
  CONFIGURE: {
    handler: async (bot, params) => await behaviors.autonomy.configure(bot, params.mode, params.setting),
    slot: 'cognitive',
    concurrent: true,
  },
  MOVE: {
    handler: executeMove,
    slot: 'physical',
    concurrent: false,
  },
  MINE: {
    handler: executeMine,
    slot: 'physical',
    concurrent: false,
  },
  GATHER: {
    handler: async (bot, params) => await behaviors.survival.gatherResource(bot, params.resource, params.count),
    slot: 'physical',
    concurrent: false,
  },
  HUNT: {
    handler: async (bot, params) => await behaviors.combat.huntCreature(bot, params.creature_name, params.count),
    slot: 'physical',
    concurrent: false,
  },
  COLLECT_ITEM: {
    handler: async (bot, params) => await behaviors.survival.findAndCollect(bot, params.item_name, params.count),
    slot: 'physical',
    concurrent: false,
  },
  CRAFT: {
    handler: executeCraft,
    slot: 'physical',
    concurrent: false,
  },
  EQUIP: {
    handler: executeEquip,
    slot: 'cognitive',
    concurrent: true,
  },
  IDLE: {
    handler: async () => 'Idling',
    slot: null,
    concurrent: true,
  },
  STOP: {
    handler: async () => 'Stopped',
    slot: 'physical',
    concurrent: false,
  },
  SET_COMBAT_MODE: {
    handler: executeSetCombatMode,
    slot: 'physical',
    concurrent: false,
  },
  BUILD: {
    handler: async (bot, params) => await behaviors.building.buildStructure(bot, params.shape, params.material, params.dimensions, params.location),
    slot: 'physical',
    concurrent: false,
  },
  PLACE_BLOCK: {
    handler: async (bot, params) => {
      let placePos = null;
      if (params.position) {
        const pCoords = params.position.match(/(-?\d+)\s+(-?\d+)\s+(-?\d+)/);
        if (pCoords) {
          placePos = new Vec3(parseInt(pCoords[1]), parseInt(pCoords[2]), parseInt(pCoords[3]));
        }
      }
      if (!placePos && !params.near_block) {
        placePos = bot.entity.position.offset(0, -1, 0).floor();
      }
      return await behaviors.building.placeBlock(bot, params.block_name, placePos, params.near_block);
    },
    slot: 'physical',
    concurrent: false,
  },
  INSPECT_ZONE: {
    handler: async (bot, params) => {
      const c1 = params.corner1.match(/(-?\d+)\s+(-?\d+)\s+(-?\d+)/);
      const c2 = params.corner2.match(/(-?\d+)\s+(-?\d+)\s+(-?\d+)/);
      if (!c1 || !c2) throw new Error('Invalid Coordinates');
      const v1 = new Vec3(parseInt(c1[1]), parseInt(c1[2]), parseInt(c1[3]));
      const v2 = new Vec3(parseInt(c2[1]), parseInt(c2[2]), parseInt(c2[3]));
      const blocks = await behaviors.building.inspectZone(bot, v1, v2);
      return { signal: 'ZoneInspected', data: blocks };
    },
    slot: 'physical',
    concurrent: false,
  },
  SMELT: {
    handler: async (bot, params) => await behaviors.automation.smeltItem(bot, params.item_name, params.fuel_name, params.count),
    slot: 'physical',
    concurrent: false,
  },
  DEPOSIT: {
    handler: async (bot, params) => await behaviors.automation.depositToChest(bot, params.item_name, params.count),
    slot: 'physical',
    concurrent: false,
  },
  FARM: {
    handler: async (bot, params) => await behaviors.automation.farmLoop(bot, params.mode, params.crop_name, params.count),
    slot: 'physical',
    concurrent: false,
  },
  CLEAR_AREA: {
    handler: async (bot, params) => {
      const cc1 = params.corner1.match(/(-?\d+)\s+(-?\d+)\s+(-?\d+)/);
      const cc2 = params.corner2.match(/(-?\d+)\s+(-?\d+)\s+(-?\d+)/);
      if (!cc1 || !cc2) throw new Error('Invalid Coordinates');
      const cv1 = new Vec3(parseInt(cc1[1]), parseInt(cc1[2]), parseInt(cc1[3]));
      const cv2 = new Vec3(parseInt(cc2[1]), parseInt(cc2[2]), parseInt(cc2[3]));
      return await behaviors.building.clearArea(bot, cv1, cv2);
    },
    slot: 'physical',
    concurrent: false,
  },
  INVENTORY: {
    handler: async (bot, params) => await behaviors.survival.manageInventory(bot, params.task),
    slot: 'cognitive',
    concurrent: true,
  },
  INTERACT: {
    handler: executeInteract,
    slot: 'physical',
    concurrent: false,
  },
  BREAK_BLOCK: {
    handler: executeBreakBlock,
    slot: 'physical',
    concurrent: false,
  },
  THROW_ITEM: {
    handler: async (bot, params) => await behaviors.survival.throwItem(bot, params.item_name, params.count),
    slot: 'cognitive',
    concurrent: true,
  },
  USE_ITEM: {
    handler: async (bot, params) => await behaviors.survival.useItem(bot, params.item_name),
    slot: 'cognitive',
    concurrent: true,
  },
  MOUNT: {
    handler: async (bot, params) => await behaviors.survival.mountEntity(bot, params.target),
    slot: 'physical',
    concurrent: false,
  },
  DISMOUNT: {
    handler: async (bot) => await behaviors.survival.dismountEntity(bot),
    slot: 'physical',
    concurrent: false,
  },
  SLEEP: {
    handler: async (bot) => await behaviors.survival.sleep(bot),
    slot: 'physical',
    concurrent: false,
  },
  WAKE: {
    handler: async (bot) => await behaviors.survival.wake(bot),
    slot: 'physical',
    concurrent: false,
  },
  SET_EXPLORATION_MODE: {
    handler: executeSetExplorationMode,
    slot: 'physical',
    concurrent: false,
  },
  TRADE: {
    handler: async (bot, params) => await behaviors.survival.trade(bot, params.target, params.choice_index, params.count),
    slot: 'physical',
    concurrent: false,
  },
  ENCHANT: {
    handler: async (bot, params) => await behaviors.survival.enchantItem(bot, params.item_name, params.choice),
    slot: 'physical',
    concurrent: false,
  },
  REPAIR: {
    handler: async (bot, params) => await behaviors.survival.repairItem(bot, params.item_name, params.mode, params.new_name),
    slot: 'physical',
    concurrent: false,
  },
  WITHDRAW: {
    handler: async (bot, params) => await behaviors.survival.withdrawFromContainer(bot, params.item_name, params.count, params.container),
    slot: 'physical',
    concurrent: false,
  },
  USE_ON: {
    handler: async (bot, params) => await behaviors.survival.useItemOn(bot, params.item_name, params.target_block, params.target_entity, params.entity_name),
    slot: 'physical',
    concurrent: false,
  },
  FISH: {
    handler: async (bot, params) => await behaviors.survival.fish(bot),
    slot: 'physical',
    concurrent: false,
  },
};

function getHandler(action) {
  return registry[action] || null;
}

function getSlot(action) {
  const entry = registry[action];
  return entry ? entry.slot : null;
}

function isConcurrent(action) {
  const entry = registry[action];
  return entry ? entry.concurrent : true;
}

module.exports = { registry, getHandler, getSlot, isConcurrent };
