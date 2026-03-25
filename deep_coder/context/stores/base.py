from abc import ABC, abstractmethod


class SessionStoreBase(ABC):
    @abstractmethod
    def list_sessions(self) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def open(self, locator: dict | None = None):
        raise NotImplementedError

    @abstractmethod
    def save(self, session) -> None:
        raise NotImplementedError

