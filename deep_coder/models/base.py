from abc import ABC, abstractmethod


class ModelBase(ABC):
    @abstractmethod
    def __init__(self, config):
        raise NotImplementedError

    @abstractmethod
    def complete(self, request: dict) -> dict:
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def manifest() -> dict:
        raise NotImplementedError

