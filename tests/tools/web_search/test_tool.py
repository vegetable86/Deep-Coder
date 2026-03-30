import json
from types import SimpleNamespace

import pytest

from deep_coder.config import RuntimeConfig
from deep_coder.tools.web_search.providers.base import SearchResult
from deep_coder.tools.web_search.providers.factory import build_provider
from deep_coder.tools.web_search.tool import WebSearchTool


class FakeProvider:
    def __init__(self, results=None, error=None):
        self.results = results or []
        self.error = error
        self.calls = []

    def search(self, query: str, num_results: int):
        self.calls.append((query, num_results))
        if self.error is not None:
            raise self.error
        return list(self.results)


def test_web_search_tool_returns_json_results(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    provider = FakeProvider(
        results=[
            SearchResult(
                title="Deep Coder",
                url="https://example.com/deep-coder",
                snippet="Coding agent docs",
            )
        ]
    )
    tool = WebSearchTool(
        config=RuntimeConfig.from_env(workdir=tmp_path),
        workdir=tmp_path,
        provider=provider,
    )

    result = tool.exec({"query": "deep coder"})

    assert provider.calls == [("deep coder", 5)]
    assert result.is_error is False
    assert json.loads(result.output_text) == [
        {
            "title": "Deep Coder",
            "url": "https://example.com/deep-coder",
            "snippet": "Coding agent docs",
        }
    ]


def test_web_search_tool_fetches_page_content_when_requested(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    provider = FakeProvider(
        results=[
            SearchResult(
                title="Deep Coder",
                url="https://example.com/deep-coder",
                snippet="Coding agent docs",
            )
        ]
    )
    tool = WebSearchTool(
        config=RuntimeConfig.from_env(workdir=tmp_path),
        workdir=tmp_path,
        provider=provider,
    )
    monkeypatch.setattr(
        "deep_coder.tools.web_search.tool.fetch_and_clean",
        lambda url: "Full cleaned page text",
    )

    result = tool.exec({"query": "deep coder", "num_results": 1, "fetch_content": True})

    assert json.loads(result.output_text) == [
        {
            "title": "Deep Coder",
            "url": "https://example.com/deep-coder",
            "snippet": "Coding agent docs",
            "content": "Full cleaned page text",
        }
    ]


def test_web_search_tool_wraps_search_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    provider = FakeProvider(error=RuntimeError("rate limited"))
    tool = WebSearchTool(
        config=RuntimeConfig.from_env(workdir=tmp_path),
        workdir=tmp_path,
        provider=provider,
    )

    result = tool.exec({"query": "deep coder", "num_results": 2})

    assert result.is_error is True
    assert result.output_text == "web_search failed: rate limited"


def test_build_provider_rejects_unknown_provider():
    config = SimpleNamespace(web_search_settings={"provider": "duckduckgo"})

    with pytest.raises(ValueError, match="unknown web_search provider"):
        build_provider(config)


def test_build_provider_rejects_missing_required_config():
    config = SimpleNamespace(
        web_search_settings={"provider": "google", "google": {"api_key": "test-key"}}
    )

    with pytest.raises(ValueError, match="requires 'cx'"):
        build_provider(config)
