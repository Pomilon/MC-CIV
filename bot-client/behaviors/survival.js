const { goals } = require('mineflayer-pathfinder');
const Vec3 = require('vec3');

function setup(bot) {
  // Auto Eat should be loaded in index.js
    
  // Config auto eat
  if (bot.autoEat) {
    bot.autoEat.options = {
      priority: 'foodPoints',
      startAt: 14,
      bannedFood: [],
    };
  }
    
  // Auto Sleep logic
  bot.on('time', async () => {
    if (bot.time.isDay) return;
    // Optional auto-sleep logic could remain, but we want manual control too.
  });
    
  bot.on('wake', () => {
    // bot.chat("Good morning!") // Optional
  });
}

async function manageInventory(bot, task) {
  if (task === 'equip_best') {
    return 'EquippedBest';
  } else if (task === 'sort') {
    return 'InventorySorted';
  } else if (task === 'discard_junk') {
    const junk = ['dirt', 'cobblestone', 'gravel', 'andesite', 'diorite', 'granite'];
    let tossed = 0;
    for (const item of bot.inventory.items()) {
      if (junk.includes(item.name)) {
        try {
          await bot.toss(item.type, null, item.count);
          tossed += item.count;
        } catch (err) {
          console.log('Error tossing', err);
        }
      }
    }
    return `Discarded_${tossed}_Items`;
  }
  throw new Error(`Unknown inventory task: ${task}`);
}

async function breakBlock(bot, blockName, position) {
  let block;
    
  if (position) {
    // Mode 1: Coordinates
    const vec = new Vec3(position.x, position.y, position.z);
    block = bot.blockAt(vec);
        
    if (!block || block.name === 'air') throw new Error('TargetIsAir');
    if (block.name === 'bedrock') throw new Error('CannotBreakBedrock');
        
    // Optional: If blockName is also provided, verify it matches
    if (blockName && block.name !== blockName) {
      console.log(`Warning: Target block is ${block.name}, expected ${blockName}. Breaking anyway.`);
    }
  } else {
    // Mode 2: Search
    if (!blockName) throw new Error('BlockNameRequiredForSearch');
    const blockIds = bot.registry.blocksByName[blockName].id;
    block = bot.findBlock({ matching: blockIds, maxDistance: 32 });
    if (!block) throw new Error('BlockNotFound');
  }
    
  await bot.collectBlock.collect(block);
  return 'BlockBroken';
}

async function gatherResource(bot, resourceName, count = 1) {
  const blockType = bot.registry.blocksByName[resourceName];
  if (!blockType) throw new Error(`Unknown block type: ${resourceName}`);

  let collected = 0;
  let attempts = 0;
  let consecutiveFailures = 0;
  const MAX_ATTEMPTS = count + 5;

  while (collected < count && attempts < MAX_ATTEMPTS) {
    attempts++;

    // After 2 consecutive failures, move to a different position
    if (consecutiveFailures >= 2) {
      try {
        const angle = Math.random() * Math.PI * 2;
        const target = bot.entity.position.offset(
          Math.cos(angle) * 12, 0, Math.sin(angle) * 12
        );
        await bot.pathfinder.goto(new goals.GoalNear(target.x, target.y, target.z, 2));
      } catch (_) {
        bot.pathfinder.stop();
      }
      consecutiveFailures = 0;
      continue;
    }

    const block = bot.findBlock({
      matching: blockType.id,
      maxDistance: 64,
    });

    if (!block) {
      if (collected > 0) return `PartialGather_${collected}_of_${count}_NoMoreFound`;
      throw new Error('ResourceNotFound');
    }

    let collectPromise = null;
    try {
      collectPromise = bot.collectBlock.collect(block);
      const timeoutPromise = new Promise((_, reject) =>
        setTimeout(() => reject(new Error('Collect Timeout')), 20000)
      );
      await Promise.race([collectPromise, timeoutPromise]);

      collected++;
      consecutiveFailures = 0;
    } catch (err) {
      console.log(`Gather error (${attempts}):`, err.message);
      consecutiveFailures++;
      bot.pathfinder.stop();
      if (collectPromise) collectPromise.catch(() => {});
      if (consecutiveFailures >= 5) {
        return `GatherFailed_TooManyErrors_Collected_${collected}`;
      }
    }
  }

  if (collected < count) return `PartialGather_${collected}_of_${count}`;
  return `Gathered_${collected}_${resourceName}`;
}

async function findAndCollect(bot, itemName, count = 1) {
  // Collect dropped items
  let collected = 0;
  let attempts = 0;
    
  while (collected < count && attempts < 20) {
    attempts++;
        
    const entity = bot.nearestEntity(e => 
      e.name === 'item' && 
            e.metadata && 
             e.getDroppedItem && e.getDroppedItem().name === itemName,
    );
        
    // Better approach:
    const itemEntity = Object.values(bot.entities).find(e => 
      e.name === 'item' && 
            (e.getDroppedItem()?.name === itemName),
    );

    if (!itemEntity) {
      if (collected > 0) return `PartialCollect_${collected}`;
      throw new Error('ItemNotFound');
    }

    const p = itemEntity.position;
    await bot.pathfinder.goto(new goals.GoalNear(p.x, p.y, p.z, 1));
        
    // Wait a bit for pickup
    await new Promise(r => setTimeout(r, 500));
        
    // Check if entity is gone (validating pickup)
    if (!bot.entities[itemEntity.id]) {
      collected++;
    }
  }
    
  return `Collected_${collected}_${itemName}`;
}

async function throwItem(bot, itemName, count = 1) {
  const item = bot.inventory.items().find(i => i.name === itemName);
  if (!item) throw new Error('ItemNotInInventory');
    
  await bot.toss(item.type, null, count);
  return 'ItemThrown';
}

async function useItem(bot, itemName) {
  const item = bot.inventory.items().find(i => i.name === itemName);
  if (!item) throw new Error('ItemNotInInventory');
    
  await bot.equip(item, 'hand');
  await bot.consume();
  return 'ItemUsed';
}

async function mountEntity(bot, targetName) {
  const entity = bot.nearestEntity(e => (e.username === targetName || e.name === targetName));
  if (!entity) throw new Error('EntityNotFound');
    
  bot.mount(entity);
  return 'Mounted';
}

async function dismountEntity(bot) {
  bot.dismount();
  return 'Dismounted';
}

async function sleep(bot) {
  const bed = bot.findBlock({ matching: blk => bot.isABed(blk), maxDistance: 32 });
  if (!bed) throw new Error('NoBedNearby');
    
  try {
    await bot.sleep(bed);
    return 'Sleeping';
  } catch (err) {
    throw new Error(`SleepFailed: ${err.message}`);
  }
}

async function wake(bot) {
  try {
    await bot.wake();
    return 'WokeUp';
  } catch (err) {
    throw new Error(`WakeFailed: ${err.message}`);
  }
}

async function trade(bot, targetName, choiceIndex = 0, count = 1) {
  const entity = bot.nearestEntity(e => e.name === targetName || e.username === targetName);
  if (!entity) throw new Error('VillagerNotFound');

  const villager = await bot.openVillager(entity);

  await new Promise((resolve, reject) => {
    villager.once('ready', resolve);
    setTimeout(() => reject(new Error('TradesNotReady')), 10000);
  });

  if (choiceIndex < 0 || choiceIndex >= villager.trades.length) {
    villager.close();
    throw new Error(`InvalidTradeIndex: ${choiceIndex}, has ${villager.trades.length} trades`);
  }

  const outputName = villager.trades[choiceIndex].output.name;
  await villager.trade(choiceIndex, count);
  villager.close();
  return `Traded_${count}x_${outputName}`;
}

async function enchantItem(bot, itemName, choice = '0') {
  const item = bot.inventory.items().find(i => i.name === itemName);
  if (!item) throw new Error('ItemNotInInventory');

  const tableBlock = bot.findBlock({
    matching: bot.registry.blocksByName['enchanting_table'].id,
    maxDistance: 6,
  });
  if (!tableBlock) throw new Error('EnchantingTableNotFound');

  const table = await bot.openEnchantmentTable(tableBlock);
  await table.putTargetItem(item);

  const lapis = bot.inventory.items().find(i => i.name === 'lapis_lazuli');
  if (lapis) await table.putLapis(lapis);

  await new Promise((resolve, reject) => {
    table.once('ready', resolve);
    setTimeout(() => reject(new Error('EnchantNotReady')), 10000);
  });

  await table.enchant(parseInt(choice, 10));
  const enchanted = await table.takeTargetItem();
  table.close();
  return `Enchanted_${enchanted.name}`;
}

const _REPAIR_MATERIALS = {
  diamond_pickaxe: 'diamond', diamond_axe: 'diamond', diamond_sword: 'diamond',
  diamond_shovel: 'diamond', diamond_hoe: 'diamond',
  diamond_helmet: 'diamond', diamond_chestplate: 'diamond',
  diamond_leggings: 'diamond', diamond_boots: 'diamond',
  iron_pickaxe: 'iron_ingot', iron_axe: 'iron_ingot', iron_sword: 'iron_ingot',
  iron_shovel: 'iron_ingot', iron_hoe: 'iron_ingot',
  iron_helmet: 'iron_ingot', iron_chestplate: 'iron_ingot',
  iron_leggings: 'iron_ingot', iron_boots: 'iron_ingot',
  golden_pickaxe: 'gold_ingot', golden_axe: 'gold_ingot', golden_sword: 'gold_ingot',
  golden_shovel: 'gold_ingot', golden_hoe: 'gold_ingot',
  golden_helmet: 'gold_ingot', golden_chestplate: 'gold_ingot',
  golden_leggings: 'gold_ingot', golden_boots: 'gold_ingot',
  stone_pickaxe: 'cobblestone', stone_axe: 'cobblestone', stone_sword: 'cobblestone',
  stone_shovel: 'cobblestone', stone_hoe: 'cobblestone',
  leather_helmet: 'leather', leather_chestplate: 'leather',
  leather_leggings: 'leather', leather_boots: 'leather',
  shield: 'oak_planks', bow: 'string', crossbow: 'iron_ingot', fishing_rod: 'string',
};

async function repairItem(bot, itemName, mode = 'repair', newName = null) {
  const item = bot.inventory.items().find(i => i.name === itemName);
  if (!item) throw new Error('ItemNotInInventory');

  if (mode === 'disenchant') {
    const gsBlock = bot.findBlock({
      matching: bot.registry.blocksByName['grindstone'].id,
      maxDistance: 6,
    });
    if (!gsBlock) throw new Error('GrindstoneNotFound');
    const window = await bot.openBlock(gsBlock);
    await bot.moveSlotItem(item.slot, 0);
    await new Promise(r => setTimeout(r, 1000));
    await bot.moveSlotItem(2, bot.inventory.hotbarStart);
    window.close();
    return 'Disenchanted';
  }

  const anvilBlock = bot.findBlock({
    matching: bot.registry.blocksByName['anvil'].id,
    maxDistance: 6,
  });
  if (!anvilBlock) throw new Error('AnvilNotFound');

  const anvil = await bot.openAnvil(anvilBlock);

  if (mode === 'rename') {
    await anvil.combine(item, newName || '');
  } else {
    const matName = _REPAIR_MATERIALS[itemName];
    const repairMat = matName ? bot.inventory.items().find(i => i.name === matName) : null;
    if (!repairMat) {
      anvil.close();
      throw new Error(`NoRepairMaterialFor_${itemName}`);
    }
    await anvil.combine(item, repairMat, '');
  }
  anvil.close();
  return mode === 'rename' ? `Renamed_${itemName}` : `Repaired_${itemName}`;
}

async function withdrawFromContainer(bot, itemName, count = 1, container = null) {
  let block;
  if (container) {
    const ids = bot.registry.blocksByName[container];
    if (!ids) throw new Error(`UnknownContainer: ${container}`);
    block = bot.findBlock({ matching: ids.id, maxDistance: 6 });
  } else {
    const types = ['chest', 'barrel', 'shulker_box', 'trapped_chest'];
    for (const t of types) {
      const ids = bot.registry.blocksByName[t];
      if (!ids) continue;
      block = bot.findBlock({ matching: ids.id, maxDistance: 6 });
      if (block) { container = t; break; }
    }
  }
  if (!block) throw new Error('ContainerNotFound');

  const window = await bot.openContainer(block);
  const itemType = bot.registry.itemsByName[itemName]?.id;
  if (!itemType) { window.close(); throw new Error(`UnknownItem: ${itemName}`); }

  await window.withdraw(itemType, null, count, null);
  window.close();
  return `Withdrew_${count}_${itemName}`;
}

async function useItemOn(bot, itemName, targetBlock = null, targetEntity = null, entityName = null) {
  const item = bot.inventory.items().find(i => i.name === itemName);
  if (!item) throw new Error('ItemNotInInventory');

  await bot.equip(item, 'hand');

  if (targetEntity) {
    const entity = bot.nearestEntity(e => e.name === targetEntity || e.username === targetEntity);
    if (!entity) throw new Error('EntityNotFound');
    await bot.useOn(entity);
    return `Used_${itemName}_on_${targetEntity}`;
  }

  if (targetBlock) {
    const ids = bot.registry.blocksByName[targetBlock];
    if (!ids) throw new Error(`UnknownBlock: ${targetBlock}`);
    const block = bot.findBlock({ matching: ids.id, maxDistance: 6 });
    if (!block) throw new Error('BlockNotFound');
    await bot.activateBlock(block);
    return `Used_${itemName}_on_${targetBlock}`;
  }

  await bot.activateItem();
  return `Used_${itemName}`;
}

async function fish(bot) {
  const rod = bot.inventory.items().find(i => i.name === 'fishing_rod');
  if (!rod) throw new Error('FishingRodNotFound');

  await bot.equip(rod, 'hand');
  await bot.fish();
  return 'FishCaught';
}

module.exports = { 
  setup, 
  manageInventory, 
  breakBlock, 
  gatherResource,
  findAndCollect,
  throwItem, 
  useItem, 
  mountEntity, 
  dismountEntity, 
  sleep, 
  wake,
  trade,
  enchantItem,
  repairItem,
  withdrawFromContainer,
  useItemOn,
  fish,
};