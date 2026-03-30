import httpx

from deep_coder.tools.web_search.fetch import fetch_and_clean


def test_fetch_and_clean_strips_non_content_html(monkeypatch):
    def fake_get(url, timeout):
        assert url == "https://example.com/page"
        assert timeout == 10
        return httpx.Response(
            200,
            text=(
                "<html>"
                "<head><title>Ignore me</title><style>.x { color: red; }</style></head>"
                "<body>"
                "<script>console.log('ignore')</script>"
                "<h1>Visible Title</h1>"
                "<p>Hello   world</p>"
                "<!-- comment -->"
                "<div>more text</div>"
                "</body>"
                "</html>"
            ),
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr("deep_coder.tools.web_search.fetch.httpx.get", fake_get)

    assert (
        fetch_and_clean("https://example.com/page")
        == "Visible Title Hello world more text"
    )


def test_fetch_and_clean_returns_failure_string_for_timeout(monkeypatch):
    def fake_get(url, timeout):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr("deep_coder.tools.web_search.fetch.httpx.get", fake_get)

    assert fetch_and_clean("https://example.com/page") == "fetch failed: timeout"
