from abc import ABC, abstractmethod


class PromptBase(ABC):
    @abstractmethod
    def __init__(self, config):
        raise NotImplementedError

    @abstractmethod
    def render(self, session_snapshot: dict, tool_schemas: list[dict]) -> str:
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def manifest() -> dict:
        raise NotImplementedError

