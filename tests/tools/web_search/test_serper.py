import httpx

from deep_coder.tools.web_search.providers.serper import SerperProvider


def test_serper_search_posts_payload_and_parses_results(monkeypatch):
    provider = SerperProvider(api_key="serper-key")

    def fake_post(url, headers, json, timeout):
        assert url == "https://google.serper.dev/search"
        assert headers == {"X-API-KEY": "serper-key"}
        assert json == {"q": "deep coder", "num": 4}
        assert timeout == 10
        return httpx.Response(
            200,
            json={
                "organic": [
                    {
                        "title": "Deep Coder",
                        "link": "https://example.com/deep-coder",
                        "snippet": "Serper snippet",
                    }
                ]
            },
            request=httpx.Request("POST", url, headers=headers, json=json),
        )

    monkeypatch.setattr(
        "deep_coder.tools.web_search.providers.serper.httpx.post",
        fake_post,
    )

    results = provider.search("deep coder", 4)

    assert [result.title for result in results] == ["Deep Coder"]
    assert [result.url for result in results] == ["https://example.com/deep-coder"]
    assert [result.snippet for result in results] == ["Serper snippet"]
