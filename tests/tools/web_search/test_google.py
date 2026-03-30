import httpx

from deep_coder.tools.web_search.providers.google import GoogleSearchProvider


def test_google_search_builds_request_and_parses_results(monkeypatch):
    provider = GoogleSearchProvider(api_key="google-key", cx="search-cx")

    def fake_get(url, params, timeout):
        assert url == "https://www.googleapis.com/customsearch/v1"
        assert params == {
            "key": "google-key",
            "cx": "search-cx",
            "q": "deep coder",
            "num": 3,
        }
        assert timeout == 10
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "title": "Deep Coder",
                        "link": "https://example.com/deep-coder",
                        "snippet": "Coding agent docs",
                    }
                ]
            },
            request=httpx.Request("GET", url, params=params),
        )

    monkeypatch.setattr(
        "deep_coder.tools.web_search.providers.google.httpx.get",
        fake_get,
    )

    results = provider.search("deep coder", 3)

    assert [result.title for result in results] == ["Deep Coder"]
    assert [result.url for result in results] == ["https://example.com/deep-coder"]
    assert [result.snippet for result in results] == ["Coding agent docs"]
