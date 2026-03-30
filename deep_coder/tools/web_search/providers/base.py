from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


class SearchProvider(ABC):
    @abstractmethod
    def search(self, query: str, num_results: int) -> list[SearchResult]:
        raise NotImplementedError
