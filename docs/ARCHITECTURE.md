# System Architecture

## Overview

The AI Minecraft Storytelling Server operates on a distributed **Brain-Body** architecture.

### 1. The Brain (Python)
The "Brain" is the high-level reasoning engine. It does not handle physics or real-time packet processing.
- **LLM Provider:** Abstracts specific API calls (Gemini/OpenAI) and enforces the JSON Action Grammar.
- **Agent Controller:** Maintains the "Observe-Reason-Act" loop. It manages memory (sliding window of text) and spatial knowledge (named locations).
- **Narrator:** A specialized loop that looks at the global state (not a specific player view) to direct the story.

### 2. The Body (Node.js)
The "Body" is a Mineflayer bot running in a Node.js process. It communicates with the Brain via a local HTTP API.
- **`/observe`:** Returns a JSON snapshot of the bot's senses (Health, Inventory, Nearby Entities, Chat).
- **`/act`:** Accepts high-level directives.

### 3. Directives & Behaviors
To solve the latency problem of LLMs (1-3 seconds per token generation), the system uses **Directives**.

Instead of the LLM saying "Press W key for 500ms", it says:
`{"action": "SET_COMBAT_MODE", "mode": "pvp", "target": "Steve"}`

The Node.js Body then enters a `mineflayer-pvp` loop, handling strafing, critical hits, and shielding at 20 ticks per second, autonomously.

**Supported Directives:**
- `SET_COMBAT_MODE`: Activates PvP logic.
- `SET_SURVIVAL`: Sets aggression/fear levels (Brave/Cowardly).
- `BUILD`: Executes a macro to build structures (Walls, Floors).
- `SET_EXPLORATION_MODE`: Activates random wandering or target following using `mineflayer-pathfinder`.

## Data Flow

1. **Minecraft Server** -> *Packets* -> **Node.js Bot**
2. **Node.js Bot** -> *JSON Observation* -> **Python Controller**
3. **Python Controller** -> *Prompt Construction* -> **LLM**
4. **LLM** -> *JSON Action* -> **Python Controller**
5. **Python Controller** -> *Directive* -> **Node.js Bot**
6. **Node.js Bot** -> *Autonomous Execution Loop* -> **Minecraft Server**
