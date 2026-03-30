import httpx

from deep_coder.tools.web_search.providers.base import SearchProvider, SearchResult


class BraveSearchProvider(SearchProvider):
    ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, query: str, num_results: int) -> list[SearchResult]:
        response = httpx.get(
            self.ENDPOINT,
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": self.api_key,
            },
            params={"q": query, "count": num_results},
            timeout=10,
        )
        response.raise_for_status()
        items = response.json().get("web", {}).get("results") or []
        return [
            SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("description", ""),
            )
            for item in items
        ]
