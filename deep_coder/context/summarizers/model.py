import json

from deep_coder.context.strategies.layered_history.strategy import (
    _format_think_result_text,
)
from deep_coder.context.summarizers.base import SummarizerBase


class ModelSummarizer(SummarizerBase):
    def __init__(self, model, config):
        self.model = model
        self.config = config

    def summarize_span(self, session, entries: list[dict]) -> dict:
        evidence_by_event = {
            record["event_id"]: record for record in session.evidence
        }
        transcript = []
        for entry in entries:
            evidence = evidence_by_event.get(entry["event_id"], {})
            content = evidence.get("content", "")
            if entry.get("tool_name") == "think":
                artifact_id = next(iter(entry.get("artifact_ids", [])), None)
                artifact = session.artifacts.get(artifact_id or "", {})
                content = _format_think_result_text(
                    final_content=artifact.get("metadata", {}).get("final_content", ""),
                    reasoning_content=artifact.get("reasoning_content", ""),
                )
            transcript.append(
                {
                    "event_id": entry["event_id"],
                    "turn_id": entry["turn_id"],
                    "role": entry["role"],
                    "kind": entry["kind"],
                    "tool_name": entry.get("tool_name"),
                    "content": content,
                }
            )
        response = self.model.complete(
            {
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Summarize the provided session span as compact JSON with "
                            "keys such as goal, decisions, files, constraints, and "
                            "open_questions. Return JSON only."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "session": session.meta(),
                                "max_tokens": self.config.context_summary_max_tokens,
                                "entries": transcript,
                            }
                        ),
                    },
                ],
                "tools": [],
            }
        )
        return _parse_summary(response.get("content"))


def _parse_summary(content: str | None) -> dict:
    if not content:
        return {"goal": "summarized prior context"}
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            text = "\n".join(lines[1:-1]).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {"goal": text}
    if isinstance(parsed, dict):
        return parsed
    return {"goal": text}
