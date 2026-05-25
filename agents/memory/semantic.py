import logging
from collections.abc import Callable

from agents.memory.base import SemanticMemoryBase

logger = logging.getLogger(__name__)


def _keyword_match(query: str, key: str) -> float:
    q = query.lower()
    k = key.lower()
    if q in k or k in q:
        return 1.0
    query_words = set(q.split())
    key_words = set(k.replace("_", " ").split())
    if not query_words or not key_words:
        return 0.0
    overlap = query_words & key_words
    return len(overlap) / max(len(query_words), len(key_words))


class SemanticMemory(SemanticMemoryBase):
    def __init__(self, embedding_fn: Callable | None = None):
        self.facts: dict[str, str] = {}
        self.embeddings: dict[str, list[float]] = {}
        self.embedding_fn = embedding_fn

    def store(self, key: str, value: str, tags: list[str] | None = None) -> None:
        self.facts[key] = value
        if self.embedding_fn:
            try:
                self.embeddings[key] = self.embedding_fn([key])[0]
            except Exception as e:
                logger.warning(f"Embedding failed for '{key}': {e}")

    def retrieve(self, query: str, top_k: int = 3) -> list[tuple[str, str, float]]:
        results = self._keyword_search(query, top_k)
        if results:
            return results
        if self.embedding_fn:
            return self._vector_search(query, top_k)
        return []

    def forget(self, key: str) -> None:
        self.facts.pop(key, None)
        self.embeddings.pop(key, None)

    def get_all(self) -> dict[str, str]:
        return dict(self.facts)

    def _keyword_search(self, query: str, top_k: int) -> list[tuple[str, str, float]]:
        scored = [(key, value, _keyword_match(query, key)) for key, value in self.facts.items()]
        scored.sort(key=lambda x: x[2], reverse=True)
        return [(k, v, s) for k, v, s in scored if s > 0][:top_k]

    def _vector_search(self, query: str, top_k: int) -> list[tuple[str, str, float]]:
        if not self.embedding_fn or not self.embeddings:
            return []
        try:
            query_emb = self.embedding_fn([query])[0]
            scored = []
            for key, emb in self.embeddings.items():
                score = self._cosine_similarity(query_emb, emb)
                scored.append((key, self.facts[key], score))
            scored.sort(key=lambda x: x[2], reverse=True)
            return scored[:top_k]
        except Exception as e:
            logger.warning(f"Vector search failed: {e}")
            return []

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(y * y for y in b) ** 0.5
        if not norm_a or not norm_b:
            return 0.0
        return dot / (norm_a * norm_b)

    def clear(self) -> None:
        self.facts.clear()
        self.embeddings.clear()
