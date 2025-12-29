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
- **Hybrid Intelligence:** Combines LLM reasoning (Commanders) with programmed autonomous behaviors (Soldiers).
- **Multi-Provider Support:** Plug-and-play support for **Google Gemini**, **OpenAI**, **Anthropic (Claude)**, **Groq**, and **Ollama**.
- **Autonomous Modes:**
  - **PvP Mode:** Agents can autonomously hunt and fight targets using advanced combat logic (`mineflayer-pvp`).
  - **Exploration:** Agents can wander or follow specific targets autonomously.
  - **Survival:** Auto-eating, auto-sleeping, and inventory management.
  - **Building:** Capable of executing construction macros (walls, floors) on command.
- **Location Memory:** Agents remember key locations (e.g., "Home", "Base") and can navigate back to them.
- **Proximity Chat:** Agents communicate with players nearby, respecting conversation turns.

### 🏗 Architecture
- **Commander-Executor Pattern:** To avoid LLM latency lag, the Python backend ("Commander") issues high-level directives (e.g., `SET_COMBAT_MODE`), while the Node.js client ("Executor") handles the tick-perfect execution.
- **Strict Grammar:** Uses a typed JSON grammar to ensure reliable LLM outputs (no hallucinations in commands).
- **Persistence:** Agent memories and locations are saved to disk, persisting across restarts.

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
   # Gemini
   python cli/main.py --mode real --provider gemini --bots 2

   # Claude (Anthropic)
   python cli/main.py --mode real --provider claude --bots 2

   # Local Ollama
   python cli/main.py --mode real --provider ollama --model llama3.1
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

- `agents/`: Python logic for the Agent Brain (LLM interaction, Memory, Controller).
- `bot-client/`: Node.js/Mineflayer application for the Agent Body (Physics, Pathfinding, PvP).
- `narrator/`: Logic for the Global Storyteller.
- `infrastructure/`: RCON and Game State APIs.
- `cli/`: Entry point and process management.
- `tests/`: Comprehensive unit tests.

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