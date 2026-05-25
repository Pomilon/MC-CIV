# System Architecture

## Overview

MC-CIV uses a **Brain-Body (Commander-Executor)** architecture: a Python backend
("Brain") handles LLM reasoning and emits high-level directives, while a Node.js
Mineflayer client ("Body") executes those directives with real-time physics and
pathfinding.

The Brain is now a proper **agentic framework** with memory, tools, observation
rendering, and context management — not just prompt engineering.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        BRAIN (Python)                               │
│                                                                     │
│  ┌────────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │  Memory     │  │  Tools   │  │ Context  │  │  Observation     │ │
│  │  Manager    │  │  Registry│  │ Builder  │  │  Renderer        │ │
│  │             │  │          │  │          │  │                  │ │
│  │  · Working  │  │  · Body  │  │  · Token │  │  · CONText       │ │
│  │  · Episodic │  │  · Cog   │  │  · Prio  │  │  · NEARBY       │ │
│  │  · Semantic │  │  · Decl  │  │  · Summ  │  │  · STATUS       │ │
│  └──────┬──────┘  └────┬─────┘  └────┬─────┘  │  · EVENTS       │ │
│         │              │             │         │  · CHAT         │ │
│         └──────────────┴─────────────┴─────────┘──────────────────┘ │
│                           │                                         │
│                    ┌──────▼──────┐                                  │
│                    │ Agent Loop  │  (ReAct: Observe→Reason→Act→Mem) │
│                    │ State:      │  SPAWNING→THINKING→EXECUTING→    │
│                    │             │  WAITING→THINKING...             │
│                    └──────┬──────┘                                  │
│                           │                                          │
│                    ┌──────▼──────┐                                  │
│                    │ LLM Core   │  (Gemini/OpenAI/Anthropic/Mock)    │
│                    └─────────────┘                                  │
└──────────────────────────┬──────────────────────────────────────────┘
                           │  WebSocket (orchestrator bus)
┌──────────────────────────▼──────────────────────────────────────────┐
│                        BODY (Node.js)                               │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────────┐ │
│  │ Action State │  │  Action      │  │  Behavior Modules         │ │
│  │              │  │  Registry    │  │                           │ │
│  │ · idle       │  │              │  │  · combat.js  · survival  │ │
│  │ · running    │  │  MOVE →      │  │  · building   · explore   │ │
│  │ · completed  │  │  CHAT →      │  │  · automation · autonomy  │ │
│  │ · failed     │  │  BUILD →     │  └───────────────────────────┘ │
│  └──────────────┘  └──────────────┘                                │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────────┐ │
│  │ WS Client    │  │ Observation  │  │ Bot Lifecycle             │ │
│  │              │  │              │  │                           │ │
│  │ · connect    │  │ · getObs()   │  │ · initBot()               │ │
│  │ · reconnect  │  │ · loop       │  │ · cleanupBot()            │ │
│  │ · sendEvent  │  │              │  │ · plugin loading          │ │
│  └──────────────┘  └──────────────┘  └───────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

## Agent Loop (ReAct)

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ OBSERVE  │────→│  REASON  │────→│   ACT    │────→│ MEMORIZE │
│          │     │          │     │          │     │          │
│ Request  │     │ Build    │     │ Execute  │     │ Store to │
│ obs from │     │ context  │     │ tool via │     │ working  │
│ Body     │     │ + LLM    │     │ registry │     │ + episodic│
│ Render   │     │ call     │     │          │     │ + consol │
│ to text  │     │          │     │          │     │          │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
      │                                              │
      └─────────────────── loop ─────────────────────┘
```

The loop is **interruptible** — body actions are long-running and non-blocking.
See "Async Action System" below.

## Async Action System

The core design challenge: **body actions are slow (seconds to minutes)** but the
agent must remain responsive to chat, events, and environmental changes.

### Conceptual Model

```
Brain                          Body
 │                              │
 │── command:GATHER oak_log ──→ │
 │   (cmd_001)                  │── action_started(cmd_001)
 │                              │   (gathering...)
 │                              │
 │←── chat:Player_X: "hello" ──│  ← Interrupt!
 │   [fork side conversation]   │   (gathering continues)
 │── command:CHAT "hi there" ──→│
 │   (side_..., concurrent)      │── CHAT "hi there"
 │                              │   (gathering continues)
 │←── action_result(side_...) ──│   (chat done)
 │   (ignored — cmd_id mismatch) │   (gathering continues)
 │                              │
 │←── action_result(cmd_001) ──│  ← Done!
 │   [squash side conversation] │
 │   (Gathered 32 oak_log       │
 │    + summary of chat)        │
 │                              │
 │── [back to THINKING]         │
 ```

### Interruptible Wait Pattern

The agent loop does NOT block on body actions. Instead:

```
THINK → send command → WAITING_FOR_BODY:
  race: action_result(cmd matches)? → MEMORIZE → THINK
        interrupt? + pending action? → SIDE_CONVERSATION → loop
        interrupt? + no pending action? → THINK
        timeout? → request observation → THINK
```

In `WAITING_FOR_BODY` state, incoming messages are routed:
- `action_result(id=matching)` → action complete, exit wait
- `chat` / `event` → queue as interrupt, wake the loop
- `action_result(id=other)` → ignored (e.g., CHAT completing while GATHER runs — prevented by `resolve_action` cmd_id check)
- `observation` → buffer for next THINK cycle

### Interrupt Handling Flow

When an interrupt arrives while a body action is running:

1. **Fork side conversation:** The agent enters `side_conversation` state. The full conversation history is preserved (cloned from the main context), and the interrupt messages are appended. The observation is replaced with a "{action} is still running" notice.
2. **Limited toolset:** The LLM may only use: CHAT, EQUIP, INVENTORY, THROW_ITEM, USE_ITEM, CONFIGURE, IDLE, or STOP.
3. **Multiple cycles:** Each side cycle drains the interrupt queue (batching multiple chats/events). The LLM can hold multi-turn conversations while the physical action continues.
4. **Resolution** when the main action completes or STOP is issued:
   - All side turns (interrupts + responses) are compressed into a summary
   - The summary is fed into the main context alongside the action result
   - The agent returns to `thinking` state

```
WAITING_FOR_BODY → interrupt arrives → SIDE_CONVERSATION:
  ┌─ side cycle ──────────────────────┐
  │ clone full context from main      │
  │ append interrupt messages         │
  │ LLM chooses (CHAT|EQUIP|IDLE|...) │
  │ execute concurrent action         │
  │ append response to side turns     │
  │ check: main action done?          │
  └───────────────────────────────────┘
      │                              │
   done, squash                 still running, loop
      │                              │
   return to THINKING          go back to side cycle
```

**Batching:** Interrupts that arrive during LLM generation are queued. The next side cycle drains all of them in one batch, presenting them together: "2 messages while BUILD runs: Player1: hello, Player1: are you there?"

**Squashing:** When the main action completes, the side turns are compressed:
```
[Side conversation while acting]
  <- Pomilon: hello
  -> I'm building a shelter right now
  <- Pomilon: what are you doing?
  -> I'm maintaining systems while the build finishes
  [Sent CHAT command]
  [Sent IDLE command]
```
This summary is added to working memory alongside the action result.

### Concurrency Model (Body)

The Body uses a single **physical** action slot, with certain actions marked as **concurrent**:

| Type | Actions | Behavior |
|------|---------|----------|
| Physical | MOVE, GATHER, MINE, BUILD, ATTACK, HUNT, CRAFT, SMELT, FARM, DEPOSIT, TRADE, ENCHANT, REPAIR, FISH | Mutually exclusive — one at a time. New physical action cancels the old one. |
| Concurrent | CHAT, EQUIP, INVENTORY, THROW_ITEM, USE_ITEM, IDLE | Skip state management entirely — never cancel the physical slot. |

**Rules:**
- Concurrent actions skip `actionState.startAction()`/`completeAction()` — they run independently without touching the physical slot
- Python-side `_CONCURRENT_ACTIONS` set mirrors the JS `concurrent: true` flag to avoid unnecessary cancel cycles
- A new physical action while one is running = cancel the old one (latest wins)
- Cancel messages target a specific `cmd_id` — body ignores if that action already finished
- `action_result` from concurrent actions has a different `cmd_id` — brain's `resolve_action` validates the ID before resolving the pending action

**Body-side dispatch logic (action-registry.js):**

```javascript
const registry = {
  CHAT:   { handler: executeChat,   slot: null, concurrent: true },
  MOVE:   { handler: executeMove,   slot: 'physical', concurrent: false },
  GATHER: { handler: executeGather, slot: 'physical', concurrent: false },
  EQUIP:  { handler: executeEquip,  slot: null, concurrent: true },
  IDLE:   { handler: executeIdle,   slot: null, concurrent: true },
  // ...
};
```

### Edge Cases

| Scenario | Behavior |
|----------|----------|
| Interrupt during interrupt processing | Queued in order; processed on next side cycle |
| Action completes while processing interrupt | Detected at start of next side cycle → squash side conversation → return to THINKING |
| Cancel race (action finishes before cancel arrives) | Body ignores cancel if action already complete |
| Body disconnects with pending action | `PendingAction` resolved as failed; agent retries after reconnect |
| Multiple interrupts queued | Batched: "2 messages while BUILD runs: Player1: hello, Player2: hi" |
| LLM error during side conversation | Return to side cycle after backoff |
| Concurrent action result arrives (CHAT while GATHER runs) | `resolve_action` checks cmd_id — ignored since it doesn't match pending action's id |
| Idle with no action | Enters WAITING state (no `PendingAction`); interrupt triggers immediate THINK |
| STOP in side conversation | Cancel the main physical action, squash side conversation, return to THINKING |
| Action completes mid-side-cycle | Next side cycle detects no pending action → squash → return |
| Deduplicated chat | 60s dedup window per (username, message); episodic tier skips "Chat from" lines |

### Brain-side Data Structures

```python
@dataclass
class PendingAction:
    """Tracks a body action from issue to completion."""
    cmd_id: str
    action: str
    params: dict
    issued_at: float
    future: asyncio.Future["ActionResult"]
    status: Literal["running", "completed", "cancelled", "failed"] = "running"

@dataclass
class Interrupt:
    type: Literal["chat", "event", "observation"]
    data: dict
    received_at: float

class AgentSession:
    current_action: PendingAction | None
    interrupt_queue: asyncio.Queue[Interrupt]
```

### Body-side Data Structure

```javascript
// action-state.js
const state = {
  slots: {
    physical: null,     // { id, action, startedAt, ... }
    social: new Map(),  // cmd_id → { id, action, ... }
  },
};
```

## WebSocket Message Protocol

Messages flow through the Orchestrator (`orchestrator/bus.py`):

```
Brain ──ws──→ Orchestrator ──ws──→ Body
       ◄──ws──             ◄──ws──
```

**Brain → Body:**
- `{ type: "command", data: { action, ...params, id } }` — execute action
- `{ type: "request_observation", id }` — request immediate observation
- `{ type: "cancel", data: { id } }` — cancel a running action by cmd_id

**Body → Brain:**
- `{ type: "observation", data: { ... } }` — periodic or requested observation
- `{ type: "action_result", data: { id, status, endSignal, error, observation } }` — action complete/failed (id matched against pending action)
- `{ type: "chat", data: { username, message, time } }` — player chat (triggers side conversation if action running)
- `{ type: "event", data: { message, ... } }` — game events (entity killed, damage taken, etc.)
- `{ type: "spawned", data: { name } }` — bot spawned
- `{ type: "connect", data: { name, mission } }` — body connected

## State Machine

```
                    ┌──────────────┐
                    │   SPAWNING   │  Bot connecting, plugins loading
                    └──────┬───────┘
                           ↓
                    ┌──────────────┐
              ┌────→│   THINKING   │←────────── side conversation squashed
              │     └──────┬───────┘              or action completed
              │            ↓
              │     ┌──────────────┐
              │     │  EXECUTING   │  Cognitive tools or sending command to body
              │     └──────┬───────┘
              │            ↓
              │     ┌──────────────────┐
              │     │ WAITING_FOR_BODY │  Body action in flight, interruptible
              │     └───┬──────┬───────┘
              │         │      │
              │    interrupt  action
              │     +pending │ complete
              │       │      │
              │    ┌──▼───────▼──┐
              │    │    SIDE     │
              │    │ CONVERSATION│  Isolated context, limited tools
              │    │  (loop)     │  Each cycle: drain interrupts, LLM, act
              │    └──┬──────┬───┘
              │       │      │
              │    action   STOP
              │    done     issued
              │       │      │
              │    ┌──▼──────▼───┐
              │    │   SQUASH    │  Compress side turns → summary
              │    └──────┬──────┘
              │           │
              └───────────┘

    All states → ERROR → log + recover or shutdown
```

## Tool Categories

| Category | Examples | Handler | Execution | Concurrent? |
|----------|----------|---------|-----------|-------------|
| Body | MOVE, BUILD, GATHER, HUNT, CRAFT, TRADE, ENCHANT, REPAIR, FISH, etc. | Sends WS command to Body | Async, interruptible | Physical: one at a time. Concurrent (CHAT/EQUIP/INVENTORY/THROW_ITEM/USE_ITEM): always parallel. |
| Cognitive | RECALL, REMEMBER, SAVE_LOCATION, SET_GOAL, CONFIGURE | Executes locally via MemoryManager | Instant | Always |
| Side Conversation | CHAT, EQUIP, INVENTORY, THROW_ITEM, USE_ITEM, CONFIGURE, IDLE, STOP | Mixed (cognitive + body) | Isolated context, limited toolset | Same as Concurrent + STOP |

## File Layout

```
agents/
├── agent.py              # AgentController — ReAct loop (states: spawning, thinking,
│                         #   waiting_for_body, side_conversation)
├── session.py            # AgentSession — PendingAction, Interrupt, wait/race logic
├── llm_core.py           # LLM providers (Gemini, OpenAI, Anthropic, Groq, Ollama, Mock)
├── grammar.py            # 41 Pydantic action models + AgentAction union
├── config.py             # Centralized configuration
├── memory/
│   ├── __init__.py       # MemoryManager orchestrator
│   ├── base.py           # Abstract interfaces
│   ├── working.py        # Working memory (recent turns)
│   ├── episodic.py       # Episodic memory (event history)
│   └── semantic.py       # Semantic memory (facts)
├── tools/
│   ├── registry.py       # ToolRegistry (register, declare, execute)
│   ├── body_tools.py     # Body action tools (descriptions)
│   └── cognitive_tools.py # Cognitive tools (RECALL, REMEMBER, etc.)
├── context/
│   └── builder.py        # Context assembly (tiered: system → working → episodic → semantic → obs)
└── observation/
    └── renderer.py       # Observation rendering (CONTEXT, NEARBY, STATUS, EVENTS, CHAT)

narrator/
├── agent.py              # Narrator as agent (same framework)
└── grammar.py ──→ deleted (imports from agents.grammar)

bot-client/
├── index.js              # Main loop (~167 lines)
├── ws-client.js          # WebSocket connection + reconnection
├── action-state.js       # Action state machine
├── observation.js        # Observation system
├── bot-lifecycle.js      # Bot init/cleanup
├── action-registry.js    # Action dispatch registry (slot, concurrent, handler)
├── schemas.js            # Zod schemas (per-action validation)
├── pathfinder.js         # Centralized Movements builder (allow1by1towers, parkour)
├── behaviors/
│   ├── combat.js         # PvP, hunting
│   ├── building.js       # buildStructure, placeBlock, inspectZone, clearArea
│   ├── survival.js       # Craft, smelt, farm, trade, enchant, repair, fish, use_on
│   ├── exploration.js    # Wander, follow, map, find biome
│   ├── automation.js     # Auto-collect, auto-manage
│   └── autonomy.js       # Chat detection, event handling
├── utils/
│   └── chat_manager.js   # Chat cooldown management
└── tests/
    ├── mock_bot.js       # Mock bot for testing
    ├── schemas.test.js   # Zod schema validation tests
    └── test_behaviors.js # Behavior handler tests

orchestrator/
├── bus.py                # MessageBus (WebSocket routing)
└── ...

dashboard/
├── app.py                # Flask web dashboard
└── static/               # Dashboard frontend

cli/
└── main.py               # CLI entry point + process management
```
