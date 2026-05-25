const { connect, send, disconnect } = require('./ws-client');
const actionState = require('./action-state');
const { getObservation, startObservationLoop, stopObservationLoop, setChatHistory } = require('./observation');
const { initBot, cleanupBot, getBot, behaviors } = require('./bot-lifecycle');
const { getHandler, getSlot, isConcurrent } = require('./action-registry');
const { validateCommand } = require('./schemas');
const { canChat, recordChat } = require('./utils/chat_manager');

const MOCK_MODE = process.env.MOCK_MODE === 'true';
const botOptions = {
  host: process.env.MC_HOST || 'localhost',
  port: parseInt(process.env.MC_PORT) || 25565,
  username: process.env.MC_USERNAME || 'Bot1',
  auth: 'offline',
};

const chatHistory = [];

function sendActionResult(id, status, signal, error, observation) {
  send('action_result', { id, status, endSignal: signal, error, observation });
}

async function handleCommand(payload) {
  const { id, say } = payload || {};
  const validation = validateCommand(payload);
  if (!validation.success) {
    console.error('Invalid Command:', validation.error);
    sendActionResult(id, 'failed', 'InvalidCommand', validation.error.message);
    return;
  }

  const { action, ...params } = validation.data;
  console.log(`[${botOptions.username}] Recv:`, action, params);

  if (say) {
    const bot = getBot();
    if (bot) bot.chat(say);
  }

  if (action === 'CHAT') {
    const bot = getBot();
    if (bot && canChat(bot)) {
      bot.chat(params.message);
      recordChat(bot);
      chatHistory.push({ username: bot.username, message: params.message, time: Date.now() });
    }
    const obs = getObservation(getBot(), actionState.getState());
    sendActionResult(id, 'completed', 'MessageSent', null, obs);
    return;
  }

  const handler = getHandler(action);
  if (!handler) {
    sendActionResult(id, 'failed', 'UnknownAction', `No handler for ${action}`);
    return;
  }

  const slot = getSlot(action);
  const concurrent = isConcurrent(action);

  // Concurrent actions (EQ, INV, CONFIGURE, USE_ITEM, THROW_ITEM): run without state,
  // they don't cancel pending physical actions and don't need slot tracking.
  if (concurrent && action !== 'STOP') {
    const bot = getBot();
    if (!bot || !bot.entity) {
      const obs = getObservation(null, actionState.getState());
      sendActionResult(id, 'failed', 'BotNotReady', null, obs);
      return;
    }
    try {
      const result = await handler.handler(bot, params);
      const signal = typeof result === 'string' ? result : result.signal || 'Done';
      const obs = getObservation(bot, actionState.getState());
      sendActionResult(id, 'completed', signal, null, obs);
    } catch (err) {
      const obs = getObservation(bot, actionState.getState());
      sendActionResult(id, 'failed', null, err.message || String(err), obs);
    }
    return;
  }

  const { cancelled, previousId, entry } = actionState.startAction(id, action, params, slot);

  if (cancelled && previousId) {
    const bot = getBot();
    if (bot) {
      bot.pathfinder.stop();
      if (bot.collectBlock && typeof bot.collectBlock.cancelTask === 'function') {
        bot.collectBlock.cancelTask().catch(() => {});
      }
      if (bot.pvp) bot.pvp.stop();
    }
  }

  send('action_started', { id, action });

  if (MOCK_MODE) {
    await new Promise(resolve => setTimeout(resolve, 500));
    const obs = getObservation(getBot(), actionState.getState());
    actionState.completeAction(id, 'MockSuccess', obs, slot);
    sendActionResult(id, 'completed', 'MockSuccess', null, obs);
    return;
  }

  const bot = getBot();
  if (!bot || !bot.entity) {
    actionState.failAction(id, 'BotNotReady', slot);
    sendActionResult(id, 'failed', 'BotNotReady', null, getObservation(null, actionState.getState()));
    return;
  }

  try {
    const result = await handler.handler(bot, params);
    const signal = typeof result === 'string' ? result : result.signal || 'Done';
    const data = result.data || null;
    const obs = getObservation(bot, actionState.getState());
    actionState.completeAction(id, signal, obs, slot);
    sendActionResult(id, 'completed', signal, null, obs);
  } catch (err) {
    console.error('Action Error:', err);
    const obs = getObservation(bot, actionState.getState());
    actionState.failAction(id, err.message || String(err), slot);
    sendActionResult(id, 'failed', null, err.message || String(err), obs);
  }
}

function handleMessage(message) {
  if (message.type === 'command') {
    handleCommand(message.data);
  } else if (message.type === 'request_observation') {
    const bot = getBot();
    const obs = getObservation(bot, actionState.getState());
    if (obs) send('observation', obs);
  } else if (message.type === 'cancel') {
    const { id } = message.data || {};
    actionState.stopCurrentAction(id || 'Cancelled');
    const bot = getBot();
    if (bot && bot.pathfinder) bot.pathfinder.stop();
    if (bot && bot.pvp) bot.pvp.stop();
  }
}

// --- Chat handling ---
function onChat(bot, username, message) {
  const player = bot.players[username];
  const isNearby = player && player.entity && bot.entity.position.distanceTo(player.entity.position) < 50;
  const isMention = message.toLowerCase().includes(bot.username.toLowerCase());

  if (isNearby || isMention) {
    const entry = { username, message, time: Date.now(), nearby: isNearby, mention: isMention };
    chatHistory.push(entry);
    if (chatHistory.length > 50) chatHistory.shift();
    send('chat', entry);
  }
  setChatHistory(chatHistory);
}

// --- Spawn handling ---
function onSpawned(bot, status) {
  if (status === 'disconnected') return;
  send('spawned', { name: botOptions.username });
}

// --- Start ---
const bot = initBot(botOptions, { onSpawned, onChat });
connect(botOptions.username, handleMessage);
startObservationLoop(bot, send, () => actionState.getState());
