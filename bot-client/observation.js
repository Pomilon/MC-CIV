const MOCK_MODE = process.env.MOCK_MODE === 'true';

let observationInterval = null;
let chatHistory = [];

function setChatHistory(history) {
  chatHistory = history;
}

function getObservation(bot, actionState) {
  if (!bot) return null;

  if (MOCK_MODE) {
    return {
      name: process.env.MC_USERNAME || 'Bot1',
      health: 20,
      food: 20,
      position: { x: 100, y: 64, z: 100 },
      inventory: [],
      nearby_entities: [],
      nearby_blocks: [],
      chat_history: chatHistory.slice(-5),
      time: 6000,
      mission: process.env.MISSION || 'Survive and Explore',
      action_state: actionState,
    };
  }

  if (!bot.entity) return null;

  const nearbyBlocks = bot.findBlocks({
    matching: (blk) => {
      return blk.name !== 'air' && blk.name !== 'grass_block' && blk.name !== 'dirt' && blk.name !== 'stone';
    },
    maxDistance: 8,
    count: 20,
  }).map(pos => bot.blockAt(pos).name);
  const uniqueBlocks = [...new Set(nearbyBlocks)];

  return {
    name: bot.username,
    health: bot.health,
    food: bot.food,
    position: bot.entity.position,
    inventory: bot.inventory.items().map(item => ({ name: item.name, count: item.count })),
    nearby_entities: Object.values(bot.entities)
      .filter(e => e.id !== bot.entity.id && bot.entity.position.distanceTo(e.position) < 15)
      .map(e => ({ type: e.type, name: e.username || e.displayName || e.mobType, position: e.position })),
    nearby_blocks: uniqueBlocks,
    chat_history: chatHistory.slice(-5),
    time: bot.time ? bot.time.timeOfDay : 0,
    mission: process.env.MISSION || 'Survive and Explore',
    action_state: actionState,
  };
}

function startObservationLoop(bot, sendFn, getActionState) {
  if (observationInterval) clearInterval(observationInterval);
  observationInterval = setInterval(() => {
    const obs = getObservation(bot, getActionState());
    if (obs) sendFn('observation', obs);
  }, 2000);
}

function stopObservationLoop() {
  if (observationInterval) clearInterval(observationInterval);
  observationInterval = null;
}

module.exports = {
  getObservation, startObservationLoop, stopObservationLoop, setChatHistory,
};
