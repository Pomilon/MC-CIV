// bot-client/lifecycle.js
const { spawn } = require('child_process');

class BotManager {
    constructor() {
        this.processes = new Map();
    }

    startBot(botId, config) {
        if (this.processes.has(botId)) {
            console.log(`Bot ${botId} already running.`);
            return;
        }

        const env = { ...process.env, ...config, BOT_ID: botId };
        const child = spawn('node', ['index.js'], { env });

        child.stdout.on('data', (data) => {
            console.log(`[${botId}] ${data}`);
        });

        child.stderr.on('data', (data) => {
            console.error(`[${botId}] ERROR: ${data}`);
        });

        child.on('close', (code) => {
            console.log(`[${botId}] exited with code ${code}`);
            this.processes.delete(botId);
        });

        this.processes.set(botId, child);
        console.log(`Started bot ${botId}`);
    }

    stopBot(botId) {
        const child = this.processes.get(botId);
        if (child) {
            child.kill();
            this.processes.delete(botId);
            console.log(`Stopped bot ${botId}`);
        }
    }
}

// Simple CLI for testing if run directly
if (require.main === module) {
    const manager = new BotManager();
    // manager.startBot('test-bot', { MC_USERNAME: 'TestBot' });
}

module.exports = BotManager;
