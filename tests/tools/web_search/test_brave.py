import httpx

from deep_coder.tools.web_search.providers.brave import BraveSearchProvider


def test_brave_search_builds_request_and_parses_results(monkeypatch):
    provider = BraveSearchProvider(api_key="brave-key")

    def fake_get(url, headers, params, timeout):
        assert url == "https://api.search.brave.com/res/v1/web/search"
        assert headers == {
            "Accept": "application/json",
            "X-Subscription-Token": "brave-key",
        }
        assert params == {"q": "deep coder", "count": 2}
        assert timeout == 10
        return httpx.Response(
            200,
            json={
                "web": {
                    "results": [
                        {
                            "title": "Deep Coder",
                            "url": "https://example.com/deep-coder",
                            "description": "Brave snippet",
                        }
                    ]
                }
            },
            request=httpx.Request("GET", url, headers=headers, params=params),
        )

    monkeypatch.setattr(
        "deep_coder.tools.web_search.providers.brave.httpx.get",
        fake_get,
    )

    results = provider.search("deep coder", 2)

    assert [result.title for result in results] == ["Deep Coder"]
    assert [result.url for result in results] == ["https://example.com/deep-coder"]
    assert [result.snippet for result in results] == ["Brave snippet"]
