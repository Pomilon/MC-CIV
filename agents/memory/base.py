from abc import ABC, abstractmethod


class WorkingMemoryBase(ABC):
    @abstractmethod
    def add(self, turn: dict) -> None: ...

    @abstractmethod
    def get_context(self) -> str: ...

    @abstractmethod
    def get_recent(self, n: int) -> list[dict]: ...


class EpisodicMemoryBase(ABC):
    @abstractmethod
    def add(self, event: str, importance: float, tags: list[str] | None = None, location: str | None = None) -> None: ...

    @abstractmethod
    def get_recent(self, k: int) -> list[dict]: ...

    @abstractmethod
    def get_important(self, threshold: float) -> list[dict]: ...

    @abstractmethod
    def get_by_tag(self, tag: str) -> list[dict]: ...

    @abstractmethod
    def consolidate(self) -> list[str]: ...


class SemanticMemoryBase(ABC):
    @abstractmethod
    def store(self, key: str, value: str, tags: list[str] | None = None) -> None: ...

    @abstractmethod
    def retrieve(self, query: str, top_k: int = 3) -> list[tuple[str, str, float]]: ...

    @abstractmethod
    def forget(self, key: str) -> None: ...

    @abstractmethod
    def get_all(self) -> dict[str, str]: ...


class MemoryManagerBase(ABC):
    working: WorkingMemoryBase
    episodic: EpisodicMemoryBase
    semantic: SemanticMemoryBase

    @abstractmethod
    def add_turn(self, turn: dict) -> None: ...

    @abstractmethod
    def add_event(self, event: str, importance: float, tags: list[str] | None = None, location: str | None = None) -> None: ...

    @abstractmethod
    def add_fact(self, key: str, value: str, tags: list[str] | None = None) -> None: ...

    @abstractmethod
    def build_context(self) -> str: ...

    @abstractmethod
    def consolidate(self) -> None: ...

    @abstractmethod
    def save(self, path: str) -> None: ...

    @classmethod
    @abstractmethod
    def load(cls, path: str) -> "MemoryManagerBase": ...
