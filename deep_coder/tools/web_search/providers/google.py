import httpx

from deep_coder.tools.web_search.providers.base import SearchProvider, SearchResult


class GoogleSearchProvider(SearchProvider):
    ENDPOINT = "https://www.googleapis.com/customsearch/v1"

    def __init__(self, api_key: str, cx: str):
        self.api_key = api_key
        self.cx = cx

    def search(self, query: str, num_results: int) -> list[SearchResult]:
        response = httpx.get(
            self.ENDPOINT,
            params={
                "key": self.api_key,
                "cx": self.cx,
                "q": query,
                "num": num_results,
            },
            timeout=10,
        )
        response.raise_for_status()
        items = response.json().get("items") or []
        return [
            SearchResult(
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=item.get("snippet", ""),
            )
            for item in items
        ]
