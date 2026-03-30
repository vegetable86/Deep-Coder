import httpx

from deep_coder.tools.web_search.providers.base import SearchProvider, SearchResult


class SerperProvider(SearchProvider):
    ENDPOINT = "https://google.serper.dev/search"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, query: str, num_results: int) -> list[SearchResult]:
        response = httpx.post(
            self.ENDPOINT,
            headers={"X-API-KEY": self.api_key},
            json={"q": query, "num": num_results},
            timeout=10,
        )
        response.raise_for_status()
        items = response.json().get("organic") or []
        return [
            SearchResult(
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=item.get("snippet", ""),
            )
            for item in items
        ]
