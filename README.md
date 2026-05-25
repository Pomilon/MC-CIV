# AI-Powered Minecraft Storytelling Server

> **⚠️ EARLY ALPHA PREVIEW**
> 
> This project is currently in **active, early development**. While the core features are functional, you may encounter bugs, unexpected agent behaviors, or stability issues. 
> 
> The AI agents are autonomous and unpredictable. They might ignore you, get stuck, or accidentally burn down their own house. **Please report any issues or weird behaviors on the [Issues](https://github.com/Pomilon/MC-CIV/issues) page.** Your feedback is crucial to making this system smarter and more robust!

An autonomous, multi-agent system designed to turn a Minecraft server into a living, breathing story. This project integrates high-level narrative AI with a swarm of LLM-driven agents (bots) that can explore, fight, build, and interact with players autonomously.

## 📖 Project Philosophy

This project was born from a love for **scripted Minecraft servers** and **Minecraft ARGs (Alternate Reality Games)**. The goal was to create a system that replicates that immersive, story-driven environment dynamically, without the need for pre-written scripts or human actors.

Instead of rigid NPC scripts, this system uses Large Language Models (LLMs) to power a **World Narrator** that directs the flow of the story and an **Agent Swarm** that lives within the world, reacting to the narrator and players in real-time.

## ✨ Features

### 🧠 The World Narrator
- **Autonomously Directors:** Polls the server state (players, time, weather) to generate narrative interventions.
- **Dynamic Events:** Can trigger weather changes, spawn entities, and broadcast story messages to players.
- **RCON Integration:** Directly interfaces with the Minecraft server console.

### 🤖 The Agent Swarm
- **Hybrid Intelligence:** Combines LLM reasoning (Brain) with a Node.js Mineflayer client (Body).
- **Multi-Provider Support:** **Google Gemini**, **OpenAI**, **Anthropic (Claude)**, **Groq**, and **Ollama**.
- **Interruptible Actions:** Agents can chat, equip, and manage inventory while a physical action (move, build, gather) is running — no need to wait.
- **Side Conversation:"** When a player chats during a long action, the agent forks into a temporary context with limited tools (chat, equip, inventory) instead of losing its train of thought. When the action completes, the side exchange is squashed into a summary.
- **Autonomous Modes:**
  - **PvP:** Hunt and fight targets using `mineflayer-pvp`.
  - **Exploration:** Wander, follow, systemically map, or find biomes.
  - **Survival:** Auto-eat, auto-sleep, farm, smelt, craft, enchant, repair, fish, and trade with villagers.
  - **Building:** Construction macros (walls, floors, boxes, towers, pyramids, stairs).
  - **Inventory:** Auto-sort, equip best, discard junk.
- **41 Action Tools:** MOVE, GATHER, MINE, BUILD, CRAFT, SMELT, CHAT, TRADE, ENCHANT, REPAIR, DEPOSIT, WITHDRAW, USE_ON (shear, milk, bone meal, flint & steel, brush, leash, name tag, saddle, bottle, honeycomb, tame/breed), FISH, HUNT, FARM, and more.
- **Memory System:** Three-layer memory (working/episodic/semantic) with automatic consolidation.
- **Proximity Chat:** Agents hear players within 50 blocks and respond via LLM.

### 🏗 Architecture
- **Brain-Body (Commander-Executor) Pattern:** The Python backend ("Brain") issues high-level directives, while the Node.js Mineflayer client ("Body") handles real-time physics, pathfinding, and block interaction.
- **Strict Grammar:** Pydantic models enforce typed JSON outputs from the LLM — no malformed commands.
- **WebSocket Orchestrator:** A lightweight message bus connects Brain ↔ Body, routing commands, action results, observations, and chat events.
- **Interruptible Wait Loop:** The agent never blocks. It races the pending action against the interrupt queue, remaining responsive to chat and events.

## 🚀 Getting Started

### Prerequisites
- **Minecraft Java Edition** (Server version 1.16.5 - 1.20.x recommended).
- **Python 3.12+**
- **Node.js 18+**
- An API Key for one of the following:
  - **Google Gemini** (Recommended, free tier available)
  - **OpenAI**
  - **Anthropic**
  - **Groq**
  - **Ollama** (Local LLM)

### 🐳 Docker Quickstart (Recommended)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Pomilon/MC-CIV.git
   cd MC-CIV
   ```

2. **Configure Environment:**
   Copy `.env.example` to `.env` and add your API keys.
   ```bash
   cp .env.example .env
   # Edit .env with your keys (GEMINI_API_KEY, ANTHROPIC_API_KEY, etc.)
   ```

3. **Start the System:**
   ```bash
   docker-compose up --build
   ```
   *Note: Ensure your Minecraft server is running and RCON is enabled in `server.properties`.*

### 🛠 Local Installation

1. **Install Python Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Install Node.js Bot Dependencies:**
   ```bash
   cd bot-client
   npm install
   cd ..
   ```

3. **Run the CLI:**
   
   **Run with Mock Mode (No Minecraft needed - great for testing):**
   ```bash
   python cli/main.py --mode mock --bots 1
   ```

   **Run with Real Server:**
   ```bash
   # Gemini (LAN world — disable narrator since RCON won't work)
   python cli/main.py --mode real --provider gemini --bots 1 --disable-narrator

   # Claude (Anthropic)
   python cli/main.py --mode real --provider claude --bots 2

   # Local Ollama
   python cli/main.py --mode real --provider ollama --model llama3.1

   # Custom Minecraft server host/port
   python cli/main.py --mode real --host 192.168.1.100 --port 44444 --bots 1
   ```

## 🧪 Testing

This project relies on a comprehensive test suite to ensure stability.

**Run Python Unit Tests (Brain):**
```bash
python3 -m unittest discover tests
```

**Run Node.js Behavior Tests (Body):**
```bash
cd bot-client
npm test
```

## 🎮 Usage

### Narrative Control
The **Narrator** runs automatically in the background. It monitors the server and will periodically inject flavor text or events based on the "Plot Points" defined in `narrator/story_engine.py`.

### Interacting with Agents
Agents appear as players in the game. You can talk to them via in-game chat.
- **PvP:** If you attack them (and they are set to Brave/Neutral), they may fight back.
- **Commands:** While they are autonomous, the LLM decides their actions based on your chat. You can try to convince them to follow you, build a house, or defend you.

## 📂 Project Structure

- `agents/`: Python Brain — LLM interaction, ReAct loop, memory system, tools, context builder, observation renderer.
- `bot-client/`: Node.js Body — Mineflayer bot, action dispatch, pathfinding, behaviors (combat, building, survival, etc.).
- `narrator/`: Global storyteller — polls server state, triggers events, broadcasts narrative.
- `orchestrator/`: WebSocket message bus that connects Brains to Bodies.
- `infrastructure/`: RCON and game state API.
- `cli/`: CLI entry point and process management.
- `dashboard/`: Web dashboard for monitoring agents.
- `tests/`: Python and JS test suites.

## 🤝 Contribution

Contributions are welcome! Since the project is in **Early Alpha**, bug reports are especially valuable.

- **Found a bug?** Open an Issue with reproduction steps.
- **Want to add a feature?** Fork the repo and submit a PR.
- **Engineering Standards:**
    - **No Placeholders:** All features must be fully implemented.
    - **Test-Driven:** New features require unit tests.
    - **Modularity:** Keep the Brain (Python) and Body (Node.js) decoupled.

## 📄 License

MIT License. See `LICENSE` for details.