# Observation System Design

## Goal

Transform raw JSON from the Body into a rich, narrative text description
of the Minecraft world that an LLM can reason about. For vision-capable models,
use screenshots instead of text for the visual parts.

## Design Philosophy

The observation is **narrative prose, not structured data.** LLMs reason better
about spatial relationships and entity interactions from descriptive text than
from JSON blobs.

Each observation is composed of **independently toggleable sections** so the
context builder can drop less important parts when tokens are tight.

## Output Format

```
=== OBSERVATION [t=time_of_day, biome=biome_name] ===

<CONTEXT> [directional description of surroundings] </CONTEXT>

<NEARBY> [entities, blocks within immediate radius] </NEARBY>

<STATUS> [health, food, inventory summary] </STATUS>

<EVENTS> [recent happenings, last action result] </EVENTS>

<CHAT> [recent chat messages] </CHAT>
```

### CONTEXT Section

The most important section. Describes what the agent "sees" around it.
Uses direction (N/S/E/W relative to agent's facing), distance qualifiers,
and point-of-interest detection.

**Input:** Agent position, facing direction, nearby blocks (up to ~20 blocks),
known locations from semantic memory.

**Output example:**
```
You are at (120, 64, -45), in a PLAINS biome at dawn.
To the NORTH: A dark oak forest with dense canopy.
To the SOUTH: A river 30 blocks away, with mountains beyond.
To the EAST: Your cobblestone home "Home Base" — 15 blocks.
To the WEST: Open plains with scattered oak trees.
```

Distance qualifiers: `nearby` (<5), `close` (5-15), `visible` (15-30), `far` (30+).
Named locations from semantic memory are injected when near.

### NEARBY Section

Details what's within immediate interaction range.

**Output example:**
```
Entities: sheep (2 grazing), zombie (1 at 12 blocks NE — hostile)
Blocks within 5m: grass, tall_grass, oak_log, crafting_table
```

Hostile entities are flagged with threat assessment.

### STATUS Section

Agent's physical state and inventory.

**Output example:**
```
Health: 18/20 | Food: 14/20 | Time since last damage: 30s
Inventory (27/36): stone_sword, cobblestone (64), oak_log (32),
  crafting_table, furnace, coal (16), cooked_beef (8)
Armor: leather_helmet (durability 35/80)
```

Inventory is summarized — only notable items. Common filler (dirt, cobble)
may be aggregated.

### EVENTS Section

Recent happenings — drawn from episodic memory.

**Output example:**
```
Last action: MOVED to Home Base — Arrived.
Events: You were attacked by a zombie. You killed it.
  Player_X: "nice job" — 2 min ago
```

### CHAT Section

Recent chat from other players.

**Output example:**
```
Player_X: "hey can you build me a house?" — 30s ago
Player_Y: "where are you?" — 2 min ago
```

## Token Budget

Default token budgets per section (configurable):

| Section | Default tokens | Drop priority |
|---------|---------------|---------------|
| CONTEXT | 200 | Last to drop (spatial awareness is critical) |
| STATUS | 100 | Fourth |
| EVENTS | 150 | Third |
| NEARBY | 100 | Second |
| CHAT | 80 | First to drop |

## Vision Support (Future)

For models that support vision (Gemini 2.0+, GPT-4o, Claude 3.5+):

1. Body captures a viewport via `prismarine-viewer` (already in deps)
2. Sends base64 screenshot directly as a vision input
3. Observation renderer produces only STATUS + EVENTS + CHAT sections
   (CONTEXT and NEARBY are replaced by the image)

Detection: the LLM provider class knows if it supports vision via a
`supports_vision` flag. The agent checks this and requests screenshot
instead of text observation from the Body.

For text-only models, the full observation is rendered as described above.

## Implementation

```python
class ObservationRenderer:
    def __init__(self, memory: MemoryManager):
        self.memory = memory

    def render(self, raw: dict, sections: set[str] = None) -> str:
        """Render observation. sections=None means all sections."""
        if sections is None:
            sections = {"context", "nearby", "status", "events", "chat"}

        lines = [f"=== OBSERVATION [t={raw.get('time', '?')}, biome={raw.get('biome', '?')}] ===\n"]

        if "context" in sections:
            lines.append(self._render_context(raw))
        if "nearby" in sections:
            lines.append(self._render_nearby(raw))
        if "status" in sections:
            lines.append(self._render_status(raw))
        if "events" in sections:
            lines.append(self._render_events())
        if "chat" in sections:
            lines.append(self._render_chat(raw))

        return "\n".join(lines)

    def _render_context(self, raw: dict) -> str:
        # Transform position + facing + block data into directional text
        # Inject named locations from semantic memory
        ...

    def _render_nearby(self, raw: dict) -> str:
        # Format entities (with threat assessment) and blocks
        ...

    def _render_status(self, raw: dict) -> str:
        # Format health, food, inventory
        ...

    def _render_events(self) -> str:
        # Get last 2-3 events from episodic memory
        ...

    def _render_chat(self, raw: dict) -> str:
        # Format recent chat from raw data
        ...
```
