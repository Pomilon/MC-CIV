import logging

from agents.memory import MemoryManager

logger = logging.getLogger(__name__)

_DISTANCE_QUALIFIERS = [
    (5, "nearby"),
    (15, "close"),
    (30, "visible"),
    (float("inf"), "far"),
]


def _qualify_distance(dist: float) -> str:
    for threshold, label in _DISTANCE_QUALIFIERS:
        if dist < threshold:
            return label
    return "far"


def _format_direction(dx: float, dz: float) -> str:
    if abs(dx) > abs(dz):
        return "EAST" if dx >= 0 else "WEST"
    else:
        return "SOUTH" if dz >= 0 else "NORTH"


_DEFAULT_SECTIONS = {"context", "nearby", "status", "events", "chat"}


class ObservationRenderer:
    def __init__(self, memory: MemoryManager):
        self.memory = memory
        self._seen_chats: set[tuple[str, str]] = set()

    def render(self, raw: dict, sections: set[str] | None = None) -> str:
        if sections is None:
            sections = _DEFAULT_SECTIONS

        time_str = raw.get("time", "?")
        biome_str = raw.get("biome", "?")
        lines = [f"=== OBSERVATION [t={time_str}, biome={biome_str}] ===", ""]

        if "context" in sections:
            lines.extend([self._render_context(raw), ""])
        if "nearby" in sections:
            lines.extend([self._render_nearby(raw), ""])
        if "status" in sections:
            lines.extend([self._render_status(raw), ""])
        if "events" in sections:
            lines.extend([self._render_events(raw), ""])
        if "chat" in sections:
            lines.extend([self._render_chat(raw), ""])

        return "\n".join(lines).rstrip()

    def _render_context(self, raw: dict) -> str:
        pos = raw.get("position", {})
        x, y, z = pos.get("x", 0), pos.get("y", 64), pos.get("z", 0)
        biome = raw.get("biome", "unknown")
        time_str = raw.get("time", "unknown")

        lines = ["<CONTEXT>"]
        lines.append(f"You are at ({x}, {y}, {z}), in a {biome.upper()} biome at {time_str}.")

        named_locations = self.memory.semantic.retrieve("location:", top_k=5)
        if named_locations:
            parts = []
            for key, loc_name, score in named_locations:
                parts.append(loc_name)
            lines.append(f"Known locations nearby: {', '.join(parts)}.")

        dirs = raw.get("direction_descriptions", {})
        if dirs:
            for d in ("north", "south", "east", "west"):
                desc = dirs.get(d)
                if desc:
                    lines.append(f"To the {d.upper()}: {desc}")

        lines.append("</CONTEXT>")
        return "\n".join(lines)

    def _render_nearby(self, raw: dict) -> str:
        lines = ["<NEARBY>"]

        entities = raw.get("entities") or raw.get("nearby_entities") or []
        if entities:
            parts = []
            for e in entities:
                name = e.get("name", "unknown")
                dist = e.get("distance", 0)
                direction = e.get("direction", "?")
                hostile = e.get("hostile", False)
                qualifier = _qualify_distance(dist)
                label = f"{name} ({qualifier}, {dist} blocks {direction})"
                if hostile:
                    label += " [HOSTILE]"
                parts.append(label)
            lines.append(f"Entities: {', '.join(parts)}.")
        else:
            lines.append("No entities nearby.")

        blocks = raw.get("nearby_blocks", [])
        if blocks:
            lines.append(f"Blocks within 5m: {', '.join(blocks)}.")
        else:
            lines.append("No notable blocks nearby.")

        lines.append("</NEARBY>")
        return "\n".join(lines)

    def _render_status(self, raw: dict) -> str:
        lines = ["<STATUS>"]
        health = raw.get("health", "?")
        food = raw.get("food", "?")
        hp_max = raw.get("max_health", 20)
        food_max = raw.get("max_food", 20)

        status_parts = []
        status_parts.append(f"Health: {health}/{hp_max}")
        status_parts.append(f"Food: {food}/{food_max}")
        status_parts.append(f"Level: {raw.get('level', '?')}")
        lines.append(" | ".join(status_parts))

        inventory = raw.get("inventory", [])
        if inventory:
            items_strs = []
            for item in inventory:
                name = item.get("name", "?")
                count = item.get("count", 1)
                items_strs.append(f"{name} ({count})" if count > 1 else name)
            lines.append(f"Inventory ({len(inventory)}): {', '.join(items_strs)}")
        else:
            lines.append("Inventory: empty.")

        if "xp" in raw:
            lines.append(f"XP: {raw['xp']}")

        lines.append("</STATUS>")
        return "\n".join(lines)

    def _render_events(self, raw: dict) -> str:
        lines = ["<EVENTS>"]

        last_action = raw.get("last_action_result", "")
        if last_action:
            lines.append(f"Last action: {last_action}")

        recent_eps = self.memory.episodic.events[-3:] if self.memory.episodic.events else []
        if recent_eps:
            for ev in recent_eps:
                text = ev["event"] if isinstance(ev, dict) else str(ev)
                if text.startswith("Chat from"):
                    continue
                lines.append(f"  {text}")

        if not lines[1:]:
            lines.append("No notable events.")

        lines.append("</EVENTS>")
        return "\n".join(lines)

    def _render_chat(self, raw: dict) -> str:
        lines = ["<CHAT>"]
        messages = raw.get("chat") or raw.get("chat_history") or []
        if messages:
            for msg in messages:
                username = msg.get("username", "?")
                text = msg.get("message", "")
                key = (username, text)
                if key in self._seen_chats:
                    continue
                self._seen_chats.add(key)
                time_ago = msg.get("time_ago", "just now")
                lines.append(f'{username}: "{text}" — {time_ago}')
        else:
            lines.append("No recent chat.")

        lines.append("</CHAT>")
        return "\n".join(lines)
