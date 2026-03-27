from abc import ABC, abstractmethod


class SummarizerBase(ABC):
    @abstractmethod
    def summarize_span(self, session, entries: list[dict]) -> dict:
        raise NotImplementedError
