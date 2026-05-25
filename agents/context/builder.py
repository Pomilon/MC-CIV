import logging

from agents import config
from agents.memory import MemoryManager

logger = logging.getLogger(__name__)


def _estimate_tokens(text: str) -> int:
    return len(text) // 4


class ContextBuilder:
    def __init__(
        self,
        memory: MemoryManager,
        system_prompt: str = "",
        profile: str = "",
        token_budget: int = config.CONTEXT_TOKEN_BUDGET,
    ):
        self.memory = memory
        self.system_prompt = system_prompt
        self.profile = profile
        self.token_budget = token_budget

    def build(self, observation: str = "", extra_context: str = "") -> list[dict[str, str]]:
        budget = self.token_budget
        messages: list[dict[str, str]] = []

        # --- Tier 0: System prompt + agent profile (always) ---
        system = self._build_system_prompt()
        messages.append({"role": "system", "content": system})
        budget -= _estimate_tokens(system)

        # --- Tier 4: Observation (dropped first if over budget) ---
        tier4 = ""
        if observation:
            tier4 = f"[Observation]\n{observation}\n"
            if extra_context:
                tier4 += f"\n[Extra]\n{extra_context}\n"

        # --- Tier 3: Semantic memory recalls ---
        tier3 = self._build_semantic_tier(budget // 4)

        # --- Tier 2: Episodic memory ---
        tier2 = self._build_episodic_tier(budget // 3)

        # --- Tier 1: Recent turns from working memory ---
        tier1_messages = self._build_tier1_turns(budget)

        total = (
            _estimate_tokens(tier4)
            + _estimate_tokens(tier3)
            + _estimate_tokens(tier2)
            + sum(_estimate_tokens(m["content"]) for m in tier1_messages)
        )
        if total > budget:
            tier3 = ""
            total = (
                _estimate_tokens(tier4)
                + _estimate_tokens(tier2)
                + sum(_estimate_tokens(m["content"]) for m in tier1_messages)
            )
        if total > budget:
            tier2 = ""
            total = (
                _estimate_tokens(tier4)
                + sum(_estimate_tokens(m["content"]) for m in tier1_messages)
            )
        while total > budget and tier1_messages:
            dropped = tier1_messages.pop(0)
            total -= _estimate_tokens(dropped["content"])

        messages.extend(tier1_messages)

        user_parts: list[str] = []
        if tier2:
            user_parts.append(tier2)
        if tier3:
            user_parts.append(tier3)
        if tier4:
            user_parts.append(tier4)

        if user_parts:
            combined = "\n".join(user_parts)
            messages.append({"role": "user", "content": combined})

        return messages

    def _build_system_prompt(self) -> str:
        parts = [self.profile] if self.profile else []
        if self.system_prompt:
            parts.append(self.system_prompt)
        parts.append(
            "You operate by observing the world, thinking about your next step, "
            "and then issuing a tool call. "
            "Only use CHAT when someone speaks to you. Do not initiate conversation. "
            "If you are waiting for something, or have no immediate goal, use the IDLE tool. "
            "Always follow player commands immediately — player instructions override your mission."
        )
        return "\n\n".join(parts)

    def _build_semantic_tier(self, max_tokens: int) -> str:
        facts = self.memory.semantic.get_all()
        if not facts:
            return ""

        lines = ["[Memory]"]
        used = 0
        for key, value in facts.items():
            line = f"  {key}: {value}"
            tokens = _estimate_tokens(line)
            if used + tokens > max_tokens:
                break
            lines.append(line)
            used += tokens
        lines.append("")
        return "\n".join(lines)

    def _build_episodic_tier(self, max_tokens: int) -> str:
        events = self.memory.episodic.events[-config.RECENT_EVENTS:] if self.memory.episodic.events else []
        if not events:
            return ""

        lines = ["[Recent Events]"]
        used = 0
        for ev in reversed(events):
            text = ev["event"] if isinstance(ev, dict) else str(ev)
            if text.startswith("Chat from"):
                continue
            line = f"  {text}"
            tokens = _estimate_tokens(line)
            if used + tokens > max_tokens:
                break
            lines.append(line)
            used += tokens
        lines.append("")
        return "\n".join(lines)

    def _build_tier1_turns(self, budget: int) -> list[dict[str, str]]:
        turns = self.memory.working.turns[-config.RECENT_TURNS:] if self.memory.working.turns else []
        messages: list[dict[str, str]] = []
        used = 0

        for turn in turns:
            turn_str = turn.get("content", "") if isinstance(turn, dict) else str(turn)
            role = turn.get("role", "user") if isinstance(turn, dict) else "user"
            tokens = _estimate_tokens(turn_str)
            if used + tokens > budget:
                break
            msg = {"role": role, "content": turn_str}
            if isinstance(turn, dict) and "tool_calls" in turn:
                msg["tool_calls"] = turn["tool_calls"]
            messages.append(msg)
            used += tokens

        return messages
