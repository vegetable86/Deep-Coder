from abc import ABC, abstractmethod


class HarnessEventSinkBase(ABC):
    @abstractmethod
    def emit(self, event: dict) -> None:
        raise NotImplementedError


class NullHarnessEventSink(HarnessEventSinkBase):
    def emit(self, event: dict) -> None:
        return None
