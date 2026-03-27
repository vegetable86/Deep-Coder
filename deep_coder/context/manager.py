import json
import uuid
from datetime import datetime, timezone

from deep_coder.context.records import make_evidence_record, make_journal_entry
from deep_coder.context.stores.base import SessionStoreBase
from deep_coder.context.strategies.base import ContextStrategyBase


class ContextManager:
    def __init__(self, store: SessionStoreBase, strategy: ContextStrategyBase):
        self.store = store
        self.strategy = strategy

    def list_sessions(self) -> list[dict]:
        return self.store.list_sessions()

    def open(self, locator: dict | None = None):
        return self.store.open(locator=locator)

    def prepare_messages(self, session, system_prompt: str, user_input: str, skill_index: str = "", active_skill_bodies: str = "") -> list[dict]:
        return self.strategy.prepare_messages(session, system_prompt, user_input, skill_index, active_skill_bodies)

    def record_event(self, session, event: dict) -> None:
        self.strategy.record_event(session, event)

    def record_user_message(self, session, turn_id: str, text: str) -> None:
        self._append_message(
            session,
            {"role": "user", "content": text},
        )
        self._record_text_event(
            session,
            turn_id=turn_id,
            kind="user_message",
            role="user",
            content=text,
        )

    def record_assistant_message(
        self,
        session,
        turn_id: str,
        text: str,
        tool_calls: list[dict] | None = None,
    ) -> None:
        message = {"role": "assistant", "content": text}
        if tool_calls:
            message["tool_calls"] = tool_calls
        self._append_message(session, message)
        if tool_calls:
            for tool_call in tool_calls:
                self.record_tool_call(session, turn_id=turn_id, tool_call=tool_call)
            return
        self._record_text_event(
            session,
            turn_id=turn_id,
            kind="assistant_message",
            role="assistant",
            content=text,
        )

    def record_tool_call(
        self,
        session,
        turn_id: str,
        tool_call: dict,
    ) -> None:
        event_id = self._next_id("evt")
        arguments = tool_call.get("arguments", {})
        journal = make_journal_entry(
            event_id=event_id,
            turn_id=turn_id,
            kind="assistant_tool_call",
            role="assistant",
            tool_name=tool_call["name"],
        )
        evidence = make_evidence_record(
            evidence_id=self._next_id("evd"),
            event_id=event_id,
            role="assistant",
            content=json.dumps(arguments, sort_keys=True),
        )
        evidence["tool_call_id"] = tool_call.get("id")
        evidence["arguments"] = arguments
        session.journal.append(journal)
        session.evidence.append(evidence)

    def record_tool_result(
        self,
        session,
        turn_id: str,
        tool_call: dict | None = None,
        output=None,
        *,
        tool_call_id: str | None = None,
        tool_name: str | None = None,
        arguments: dict | None = None,
        model_output: str | None = None,
        output_text: str | None = None,
    ) -> None:
        if tool_call is not None:
            tool_call_id = tool_call.get("id")
            tool_name = tool_call.get("name")
            arguments = tool_call.get("arguments", {})
        if output is not None:
            model_output = output.model_output
            output_text = output.output_text
            if tool_name is None:
                tool_name = output.name
        artifact_id = self._next_id("art")
        message = {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": model_output or "",
        }
        self._append_message(session, message)
        session.artifacts[artifact_id] = {
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
            "arguments": arguments or {},
            "model_output": model_output or "",
            "output_text": output_text or model_output or "",
            "display_command": getattr(output, "display_command", None),
            "diff_text": getattr(output, "diff_text", None),
            "is_error": getattr(output, "is_error", False),
        }
        event_id = self._next_id("evt")
        journal = make_journal_entry(
            event_id=event_id,
            turn_id=turn_id,
            kind="tool_result",
            role="tool",
            tool_name=tool_name,
            artifact_ids=[artifact_id],
        )
        evidence = make_evidence_record(
            evidence_id=self._next_id("evd"),
            event_id=event_id,
            role="tool",
            content=model_output or "",
            artifact_id=artifact_id,
        )
        evidence["tool_call_id"] = tool_call_id
        session.journal.append(journal)
        session.evidence.append(evidence)

    def record_summary(self, session, summary: dict) -> None:
        session.summaries.append(summary)

    def should_compact(self, session, usage: dict | None = None) -> bool:
        return self.strategy.should_compact(session, usage=usage)

    def maybe_compact(self, session, usage: dict | None = None) -> bool:
        return self.strategy.maybe_compact(session, usage=usage)

    def flush(self, session) -> None:
        self.store.save(session)

    def activate_skill(self, session, skill, *, source: str) -> tuple[dict, bool]:
        for active_skill in session.active_skills:
            if active_skill["name"] == skill.name and active_skill["hash"] == skill.content_hash:
                return active_skill, False

        session.active_skills = [
            active_skill
            for active_skill in session.active_skills
            if active_skill["name"] != skill.name
        ]
        record = {
            "name": skill.name,
            "title": skill.title,
            "hash": skill.content_hash,
            "activated_at": _utc_now(),
            "source": source,
        }
        session.active_skills.append(record)
        return record, True

    def deactivate_skill(self, session, name: str) -> bool:
        original_count = len(session.active_skills)
        session.active_skills = [
            active_skill for active_skill in session.active_skills if active_skill["name"] != name
        ]
        return len(session.active_skills) != original_count

    def clear_skills(self, session) -> list[dict]:
        cleared = list(session.active_skills)
        session.active_skills = []
        return cleared

    @staticmethod
    def _append_message(session, message: dict) -> None:
        session.append(message)

    def _record_text_event(
        self,
        session,
        turn_id: str,
        kind: str,
        role: str,
        content: str,
    ) -> None:
        event_id = self._next_id("evt")
        session.journal.append(
            make_journal_entry(
                event_id=event_id,
                turn_id=turn_id,
                kind=kind,
                role=role,
            )
        )
        session.evidence.append(
            make_evidence_record(
                evidence_id=self._next_id("evd"),
                event_id=event_id,
                role=role,
                content=content,
            )
        )

    @staticmethod
    def _next_id(prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _utc_now() -> str:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return now.replace("+00:00", "Z")
