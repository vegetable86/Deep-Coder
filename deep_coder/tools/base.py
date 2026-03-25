from abc import ABC, abstractmethod


class ToolBase(ABC):
    @abstractmethod
    def __init__(self, config, workdir):
        raise NotImplementedError

    @abstractmethod
    def exec(self, arguments: dict) -> str:
        raise NotImplementedError

    @abstractmethod
    def schema(self) -> dict:
        raise NotImplementedError

