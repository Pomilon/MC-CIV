import json
import logging
import os
import time
from collections.abc import Callable

from agents import config
from agents.memory.base import MemoryManagerBase
from agents.memory.episodic import EpisodicMemory
from agents.memory.semantic import SemanticMemory
from agents.memory.working import WorkingMemory

logger = logging.getLogger(__name__)


class MemoryManager(MemoryManagerBase):
    def __init__(
        self,
        working: WorkingMemory | None = None,
        episodic: EpisodicMemory | None = None,
        semantic: SemanticMemory | None = None,
        consolidate_interval: int = config.CONSOLIDATE_INTERVAL,
        max_tokens: int = config.WORKING_MEMORY_MAX_TOKENS,
        max_entries: int = config.EPISODIC_MEMORY_MAX_ENTRIES,
        summarizer: Callable | None = None,
        embedding_fn: Callable | None = None,
    ):
        self.working = working or WorkingMemory(max_tokens=max_tokens, summarizer=summarizer)
        self.episodic = episodic or EpisodicMemory(max_entries=max_entries)
        self.semantic = semantic or SemanticMemory(embedding_fn=embedding_fn)
        self.consolidate_interval = consolidate_interval
        self._iteration = 0

    def add_turn(self, turn: dict) -> None:
        self.working.add(turn)

    def add_event(self, event: str, importance: float, tags: list[str] | None = None, location: str | None = None) -> None:
        self.episodic.add(event, importance, tags, location)

    def add_fact(self, key: str, value: str, tags: list[str] | None = None) -> None:
        self.semantic.store(key, value, tags)

    def build_context(self) -> str:
        return self.working.get_context()

    def consolidate(self) -> None:
        self._iteration += 1
        if self._iteration % self.consolidate_interval != 0:
            return

        patterns = self.episodic.consolidate()
        for pattern in patterns:
            self.semantic.store(f"pattern:{int(time.time())}", pattern, tags=["consolidated"])

        now = time.time()
        for e in self.episodic.events[:]:
            age = now - e["timestamp"]
            if age > config.IMPORTANCE_PRUNE_AGE and e["importance"] < config.IMPORTANCE_PRUNE_THRESHOLD:
                self.episodic.events.remove(e)
                logger.debug(f"Pruned low-importance event: {e['event']}")

    def save(self, path: str) -> None:
        data = {
            "working": {
                "turns": self.working.turns,
                "summary": self.working.summary,
            },
            "episodic": {
                "events": self.episodic.events,
            },
            "semantic": {
                "facts": self.semantic.facts,
            },
        }
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Memory saved to {path}")

    @classmethod
    def load(cls, path: str, **kwargs) -> "MemoryManager":
        with open(path) as f:
            data = json.load(f)

        working = WorkingMemory(
            max_tokens=kwargs.get("max_tokens", config.WORKING_MEMORY_MAX_TOKENS),
            summarizer=kwargs.get("summarizer"),
        )
        working.turns = data.get("working", {}).get("turns", [])
        working.summary = data.get("working", {}).get("summary", "")

        episodic = EpisodicMemory(max_entries=kwargs.get("max_entries", config.EPISODIC_MEMORY_MAX_ENTRIES))
        episodic.events = data.get("episodic", {}).get("events", [])

        semantic = SemanticMemory(embedding_fn=kwargs.get("embedding_fn"))
        semantic.facts = data.get("semantic", {}).get("facts", {})

        return cls(
            working=working,
            episodic=episodic,
            semantic=semantic,
            consolidate_interval=kwargs.get("consolidate_interval", config.CONSOLIDATE_INTERVAL),
        )
