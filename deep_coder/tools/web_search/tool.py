import json
from pathlib import Path

from deep_coder.tools.base import ToolBase
from deep_coder.tools.result import ToolExecutionResult
from deep_coder.tools.web_search.fetch import fetch_and_clean


class WebSearchTool(ToolBase):
    def __init__(self, config, workdir, provider=None):
        self.config = config
        self.workdir = Path(workdir)
        self.provider = provider or getattr(config, "web_search_provider", None)

    def exec(self, arguments: dict, session=None) -> ToolExecutionResult:
        if self.provider is None:
            error_text = "web_search failed: provider not configured"
            return ToolExecutionResult(
                name="web_search",
                display_command="web_search",
                model_output=error_text,
                output_text=error_text,
                is_error=True,
            )

        query = arguments["query"]
        num_results = int(arguments.get("num_results", 5))
        fetch_content = bool(arguments.get("fetch_content", False))

        try:
            search_results = self.provider.search(query, num_results)
        except Exception as exc:
            error_text = f"web_search failed: {exc}"
            return ToolExecutionResult(
                name="web_search",
                display_command="web_search",
                model_output=error_text,
                output_text=error_text,
                is_error=True,
            )

        output = []
        for result in search_results:
            item = {
                "title": result.title,
                "url": result.url,
                "snippet": result.snippet,
            }
            if fetch_content:
                item["content"] = fetch_and_clean(result.url)
            output.append(item)

        output_text = json.dumps(output)
        return ToolExecutionResult(
            name="web_search",
            display_command="web_search",
            model_output=output_text,
            output_text=output_text,
        )

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": (
                    "Search the web using the configured provider and optionally fetch "
                    "cleaned page content for each result."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to send to the provider.",
                        },
                        "num_results": {
                            "type": "integer",
                            "description": "The number of results to return.",
                            "default": 5,
                        },
                        "fetch_content": {
                            "type": "boolean",
                            "description": (
                                "Fetch and clean the full page content for each result."
                            ),
                            "default": False,
                        },
                    },
                    "required": ["query"],
                },
            },
        }
