import logging
from collections.abc import Callable

from agents.memory.base import WorkingMemoryBase

logger = logging.getLogger(__name__)

CHARS_PER_TOKEN = 4


def _estimate_tokens(obj: list[dict]) -> int:
    total_chars = sum(len(str(t)) for t in obj)
    return total_chars // CHARS_PER_TOKEN


class WorkingMemory(WorkingMemoryBase):
    def __init__(self, max_tokens: int = 8000, summarizer: Callable | None = None):
        self.turns: list[dict] = []
        self.summary: str = ""
        self.max_tokens = max_tokens
        self.summarizer = summarizer

    def add(self, turn: dict) -> None:
        self.turns.append(turn)
        self._maybe_summarize()

    def get_context(self) -> str:
        if self.summary:
            return f"[Summary: {self.summary}]\n" + self._format_recent()
        return self._format_all()

    def get_recent(self, n: int) -> list[dict]:
        return self.turns[-n:] if self.turns else []

    def _format_all(self) -> str:
        lines = []
        for t in self.turns:
            role = t.get("role", "unknown")
            content = t.get("content", "")
            lines.append(f"[{role.upper()}] {content}")
        return "\n".join(lines)

    def _format_recent(self) -> str:
        return self._format_all()

    def _maybe_summarize(self) -> None:
        if _estimate_tokens(self.turns) <= self.max_tokens:
            return

        keep_last = 3
        oldest = self.turns[:-keep_last]
        self.turns = self.turns[-keep_last:]

        if self.summarizer and oldest:
            try:
                self.summary = self.summarizer(oldest)
            except Exception as e:
                logger.warning(f"Summarization failed: {e}")
                self.summary = self.summary or ""

    def clear(self) -> None:
        self.turns.clear()
        self.summary = ""
