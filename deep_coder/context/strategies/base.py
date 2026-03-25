from abc import ABC, abstractmethod


class ContextStrategyBase(ABC):
    @abstractmethod
    def prepare_messages(self, session, system_prompt: str, user_input: str) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def record_event(self, session, event: dict) -> None:
        raise NotImplementedError

    @abstractmethod
    def maybe_compact(self, session, usage: dict | None = None) -> None:
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def manifest() -> dict:
        raise NotImplementedError

