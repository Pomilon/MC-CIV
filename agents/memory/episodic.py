import logging
import time

from agents.memory.base import EpisodicMemoryBase

logger = logging.getLogger(__name__)


class EpisodicMemory(EpisodicMemoryBase):
    def __init__(self, max_entries: int = 200):
        self.events: list[dict] = []
        self.max_entries = max_entries

    def add(self, event: str, importance: float, tags: list[str] | None = None, location: str | None = None) -> None:
        self.events.append({
            "event": event,
            "importance": importance,
            "timestamp": time.time(),
            "location": location,
            "tags": tags or [],
        })
        self._prune()

    def get_recent(self, k: int) -> list[dict]:
        return self.events[-k:]

    def get_important(self, threshold: float) -> list[dict]:
        return [e for e in self.events if e["importance"] >= threshold]

    def get_by_tag(self, tag: str) -> list[dict]:
        return [e for e in self.events if tag in e["tags"]]

    def consolidate(self) -> list[str]:
        if len(self.events) < 3:
            return []

        tag_counts: dict[str, int] = {}
        for e in self.events:
            for t in e["tags"]:
                tag_counts[t] = tag_counts.get(t, 0) + 1

        patterns = []
        for tag, count in tag_counts.items():
            if count >= 3:
                entries = self.get_by_tag(tag)
                summary = "; ".join(e["event"][:80] for e in entries[:3])
                patterns.append(f"[{tag} x{count}] {summary}")
        return patterns

    def _prune(self) -> None:
        if len(self.events) > self.max_entries:
            self.events.sort(key=lambda e: e["importance"], reverse=True)
            self.events = self.events[:self.max_entries]

    def clear(self) -> None:
        self.events.clear()
