const WebSocket = require('ws');

let ws = null;
let reconnectInterval = 1000;
let onMessageCallback = null;

function connect(botId, onMessage) {
  onMessageCallback = onMessage;
  const wsUrl = process.env.ORCHESTRATOR_URL
    ? `${process.env.ORCHESTRATOR_URL}/body/${botId}`
    : `ws://localhost:${process.env.PORT || 3000}/ws`;

  console.log(`Connecting to Orchestrator at ${wsUrl}...`);

  ws = new WebSocket(wsUrl);

  ws.on('open', () => {
    console.log('Connected to Controller');
    reconnectInterval = 1000;
    send('connect', { name: botId, mission: process.env.MISSION || 'Survive and Explore' });
  });

  ws.on('message', (data) => {
    try {
      const message = JSON.parse(data);
      if (onMessageCallback) onMessageCallback(message);
    } catch (e) {
      console.error('Failed to parse WS message:', e);
    }
  });

  ws.on('close', () => {
    console.log('Disconnected from Controller. Retrying...');
    setTimeout(() => connect(botId, onMessageCallback), reconnectInterval);
    reconnectInterval = Math.min(reconnectInterval * 2, 30000);
  });

  ws.on('error', (err) => {
    console.error('WebSocket error:', err.message);
    ws.close();
  });
}

function send(type, data) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type, data }));
  }
}

function disconnect() {
  if (ws) {
    ws.close();
    ws = null;
  }
}

module.exports = { connect, send, disconnect };
