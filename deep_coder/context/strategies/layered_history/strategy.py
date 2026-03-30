import uuid

from deep_coder.context.records import make_summary_record
from deep_coder.context.strategies.base import ContextStrategyBase


class LayeredHistoryContextStrategy(ContextStrategyBase):
    def __init__(self, config, summarizer):
        self.config = config
        self.summarizer = summarizer

    def build_working_set(
        self,
        session,
        system_prompt: str,
        user_input: str | None,
    ) -> list[dict]:
        messages = []
        summary_message = self._rolling_summary_message(session)
        if summary_message is not None:
            messages.append(summary_message)
        if session.journal:
            messages.extend(self._recent_turn_messages(session))
        else:
            messages.extend(session.messages)
        if user_input is not None:
            messages.append({"role": "user", "content": user_input})
        return messages

    def record_event(self, session, event: dict) -> None:
        session.append(event)

    def should_compact(self, session, usage: dict | None = None) -> bool:
        if not usage:
            return False
        prompt_tokens = usage.get("prompt_tokens", 0)
        if prompt_tokens < self.config.context_max_tokens * 0.9:
            return False
        return bool(self._summarizable_entries(session))

    def maybe_compact(self, session, usage: dict | None = None) -> bool:
        if not self.should_compact(session, usage=usage):
            return False
        candidates = self._summarizable_entries(session)
        summary_payload = dict(self.summarizer.summarize_span(session, candidates))
        summary_id = summary_payload.pop("summary_id", None) or self._next_id("sum")
        covered_event_ids = [entry["event_id"] for entry in candidates]
        summary = make_summary_record(
            summary_id=summary_id,
            covered_event_ids=covered_event_ids,
            **summary_payload,
        )
        session.summaries.append(summary)
        for entry in candidates:
            entry.setdefault("summary_ids", []).append(summary_id)
        return True

    @staticmethod
    def manifest() -> dict:
        return {"name": "layered_history"}

    def _rolling_summary_message(self, session) -> dict | None:
        if not session.summaries:
            return None
        lines = ["Rolling summary:"]
        for summary in session.summaries:
            if summary.get("goal"):
                lines.append(f"Goal: {summary['goal']}")
            if summary.get("decisions"):
                lines.append(
                    "Decisions: " + ", ".join(str(item) for item in summary["decisions"])
                )
            if summary.get("files"):
                lines.append("Files: " + ", ".join(str(item) for item in summary["files"]))
            if summary.get("constraints"):
                lines.append(
                    "Constraints: "
                    + ", ".join(str(item) for item in summary["constraints"])
                )
            if summary.get("open_questions"):
                lines.append(
                    "Open questions: "
                    + ", ".join(str(item) for item in summary["open_questions"])
                )
        return {"role": "assistant", "content": "\n".join(lines)}

    def _recent_turn_messages(self, session) -> list[dict]:
        turn_ids = [
            turn_id
            for turn_id in dict.fromkeys(
                entry["turn_id"] for entry in session.journal if entry.get("turn_id")
            )
        ]
        selected_turn_ids = set(turn_ids[-self.config.context_recent_turns :])
        evidence_by_event = {
            record["event_id"]: record for record in session.evidence
        }
        messages = []
        for entry in session.journal:
            if entry.get("turn_id") not in selected_turn_ids:
                continue
            message = self._message_for_entry(
                entry,
                evidence_by_event.get(entry["event_id"]),
                session,
            )
            if message is not None:
                messages.append(message)
        return _drop_trailing_unmatched_tool_calls(messages)

    def _summarizable_entries(self, session) -> list[dict]:
        turn_ids = [
            turn_id
            for turn_id in dict.fromkeys(
                entry["turn_id"] for entry in session.journal if entry.get("turn_id")
            )
        ]
        recent_turn_ids = set(turn_ids[-self.config.context_recent_turns :])
        return [
            entry
            for entry in session.journal
            if entry.get("turn_id") not in recent_turn_ids
            and not entry.get("summary_ids")
        ]

    def _message_for_entry(self, entry: dict, evidence: dict | None, session) -> dict | None:
        role = entry.get("role")
        if role in {"user", "assistant"} and entry["kind"] != "assistant_tool_call":
            content = (evidence or {}).get("content", "")
            return {"role": role, "content": content}
        if entry["kind"] == "assistant_tool_call":
            arguments = (evidence or {}).get("arguments", {})
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": (evidence or {}).get("tool_call_id"),
                        "name": entry.get("tool_name"),
                        "arguments": arguments,
                    }
                ],
            }
        if role == "tool":
            artifact_id = next(iter(entry.get("artifact_ids", [])), None)
            artifact = session.artifacts.get(artifact_id or "", {})
            if entry.get("tool_name") == "think":
                reasoning = _truncate_reasoning(
                    artifact.get("reasoning_content", ""),
                    max_chars=self.config.context_reasoning_max_chars,
                )
                return {
                    "role": "tool",
                    "tool_call_id": (evidence or {}).get("tool_call_id"),
                    "content": _format_think_result_text(
                        final_content=artifact.get("metadata", {}).get(
                            "final_content", ""
                        ),
                        reasoning_content=reasoning,
                    ),
                }
            return {
                "role": "tool",
                "tool_call_id": (evidence or {}).get("tool_call_id"),
                "content": artifact.get("output_text") or (evidence or {}).get("content", ""),
            }
        return None

    @staticmethod
    def _next_id(prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _format_think_result_text(final_content: str, reasoning_content: str) -> str:
    return "\n".join(
        [
            "[think result]",
            "final_answer:",
            final_content,
            "",
            "reasoning_trace:",
            reasoning_content,
        ]
    )


def _truncate_reasoning(reasoning_content: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(reasoning_content) <= max_chars:
        return reasoning_content
    if max_chars <= 3:
        return reasoning_content[:max_chars]
    return f"{reasoning_content[: max_chars - 3]}..."


def _drop_trailing_unmatched_tool_calls(messages: list[dict]) -> list[dict]:
    """Remove trailing assistant tool_calls messages that have no following tool results.

    This prevents a 400 error from the API when a turn was interrupted (e.g. Ctrl+C)
    while a tool call was in flight and no tool result was ever recorded.
    """
    if not messages:
        return messages
    # Collect tool_call_ids that have a matching tool result in the list.
    answered_ids: set[str] = set()
    for msg in messages:
        if msg.get("role") == "tool" and msg.get("tool_call_id"):
            answered_ids.add(msg["tool_call_id"])
    # Walk backwards and drop assistant messages whose tool calls are all unanswered.
    result = list(messages)
    while result:
        last = result[-1]
        if last.get("role") != "assistant":
            break
        tool_calls = last.get("tool_calls")
        if not tool_calls:
            break
        call_ids = {tc.get("id") for tc in tool_calls if tc.get("id")}
        if call_ids and call_ids.isdisjoint(answered_ids):
            result.pop()
        else:
            break
    return result
