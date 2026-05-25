const mineflayer = require('mineflayer');
const { pathfinder } = require('mineflayer-pathfinder');
const collectBlock = require('mineflayer-collectblock').plugin;
const autoEatModule = require('mineflayer-auto-eat');
const autoEat = autoEatModule.loader || autoEatModule.plugin || autoEatModule.default || autoEatModule;
const Vec3 = require('vec3');
const { applyToBot } = require('./pathfinder');

const combatBehavior = require('./behaviors/combat');
const buildingBehavior = require('./behaviors/building');
const survivalBehavior = require('./behaviors/survival');
const explorationBehavior = require('./behaviors/exploration');
const autonomyBehavior = require('./behaviors/autonomy');
const automationBehavior = require('./behaviors/automation');

const MOCK_MODE = process.env.MOCK_MODE === 'true';
const MISSION = process.env.MISSION || 'Survive and Explore';

let bot = null;
let onSpawned = null;
let onChat = null;

function initBot(options, callbacks) {
  onSpawned = callbacks.onSpawned || null;
  onChat = callbacks.onChat || null;

  if (MOCK_MODE) {
    console.log('Starting in MOCK MODE');
    bot = {
      username: options.username,
      chat: (msg) => console.log(`[MOCK CHAT] ${msg}`),
      inventory: { items: () => [] },
      entity: { position: { x: 100, y: 64, z: 100 } },
      players: {},
      registry: { blocksByName: {}, itemsByName: {} },
      emit: () => {},
      on: () => {},
      once: () => {},
      removeListener: () => {},
    };
    if (onSpawned) onSpawned(bot);
    return bot;
  }

  if (bot) cleanupBot();

  console.log(`Starting bot ${options.username}...`);

  try {
    bot = mineflayer.createBot(options);
  } catch (err) {
    console.error('Failed to create bot:', err);
    setTimeout(() => initBot(options, callbacks), 10000);
    return null;
  }

  const plugins = [
    { name: 'pathfinder', plugin: pathfinder },
    { name: 'collectBlock', plugin: collectBlock },
    { name: 'autoEat', plugin: autoEat },
  ];

  for (const p of plugins) {
    if (typeof p.plugin === 'function') {
      bot.loadPlugin(p.plugin);
    } else {
      console.warn(`Warning: Plugin ${p.name} is not a function. Skipping.`);
    }
  }

  combatBehavior.setup(bot);
  buildingBehavior.setup(bot);
  survivalBehavior.setup(bot);
  explorationBehavior.setup(bot);
  autonomyBehavior.setup(bot, {
    startAction: (type, data) => {},
    stopAction: (reason) => {},
    isBusy: () => false,
    getActionType: () => null,
  });

  bot.on('spawn', () => {
    console.log('Bot spawned');
    applyToBot(bot);

    if (onSpawned) onSpawned(bot);
  });

  bot.on('chat', (username, message) => {
    if (username === bot.username) return;
    if (onChat) onChat(bot, username, message);
  });

  const handleDisconnect = (reason) => {
    console.log(`Bot disconnected: ${reason}. Reconnecting in 5s...`);
    if (onSpawned) onSpawned(null, 'disconnected');
    cleanupBot();
    setTimeout(() => initBot(options, callbacks), 5000);
  };

  bot.on('kicked', (reason) => handleDisconnect(`Kicked: ${reason}`));
  bot.on('error', (err) => handleDisconnect(`Error: ${err.message}`));
  bot.on('end', (reason) => handleDisconnect(`End: ${reason}`));

  return bot;
}

function cleanupBot() {
  if (!bot) return;
  console.log('Cleaning up bot instance...');
  bot.removeAllListeners();
  if (bot.pathfinder) bot.pathfinder.stop();
  if (bot.pvp) bot.pvp.stop();
  bot = null;
}

function getBot() {
  return bot;
}

function getBlockByName(name) {
  if (!bot) return null;
  try {
    const blockIds = bot.registry.blocksByName[name].id;
    return bot.findBlock({ matching: blockIds, maxDistance: 32 });
  } catch (e) {
    return null;
  }
}

module.exports = { initBot, cleanupBot, getBot, getBlockByName, behaviors: { combat: combatBehavior, building: buildingBehavior, survival: survivalBehavior, exploration: explorationBehavior, autonomy: autonomyBehavior, automation: automationBehavior } };
