import json

from deep_coder.tools.base import ToolBase
from deep_coder.tools.result import ToolExecutionResult


def _require_session(session):
    if session is None:
        raise ValueError("history tools require an active session")
    return session


class HistorySearchTool(ToolBase):
    def __init__(self, config, workdir):
        self.config = config
        self.workdir = workdir

    def exec(self, arguments: dict, session=None) -> ToolExecutionResult:
        session = _require_session(session)
        query = arguments["query"]
        summary_hits = _summary_hits(session, query)
        evidence_hits = _evidence_hits(session, query)
        lines = [*summary_hits, *evidence_hits]
        if not lines:
            lines = [f"No history matches for query: {query}"]
        text = "\n".join(lines)
        return ToolExecutionResult(
            name="search_history",
            display_command="search_history",
            model_output=text,
            output_text=text,
        )

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "search_history",
                "description": "Search layered session history, preferring summaries before raw evidence.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                    },
                    "required": ["query"],
                },
            },
        }


def _summary_hits(session, query: str) -> list[str]:
    hits = []
    for summary in session.summaries:
        searchable = " ".join(
            [
                str(summary.get("goal", "")),
                " ".join(summary.get("files", [])),
                " ".join(summary.get("decisions", [])),
                " ".join(summary.get("constraints", [])),
                " ".join(summary.get("open_questions", [])),
            ]
        )
        score = _match_score(query, searchable)
        if score:
            hits.append(
                (
                    score,
                    "Summary "
                    f"{summary['summary_id']}: "
                    f"{json.dumps(summary, sort_keys=True)}",
                )
            )
    return [text for _, text in sorted(hits, reverse=True)]


def _evidence_hits(session, query: str) -> list[str]:
    hits = []
    for evidence in session.evidence:
        artifact = session.artifacts.get(evidence.get("artifact_id") or "", {})
        searchable = " ".join(
            [
                evidence.get("content", ""),
                artifact.get("tool_name", ""),
                json.dumps(artifact.get("arguments", {}), sort_keys=True),
                artifact.get("output_text", ""),
            ]
        )
        score = _match_score(query, searchable)
        if score:
            hits.append(
                (
                    score,
                    "Evidence "
                    f"{evidence['evidence_id']}: "
                    f"{json.dumps(evidence, sort_keys=True)}",
                )
            )
    return [text for _, text in sorted(hits, reverse=True)]


def _match_score(query: str, text: str) -> int:
    terms = [term for term in query.lower().split() if term]
    haystack = text.lower()
    return sum(1 for term in terms if term in haystack)
