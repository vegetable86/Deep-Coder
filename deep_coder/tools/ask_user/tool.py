import json
from pathlib import Path
import sys

from deep_coder.tools.base import ToolBase
from deep_coder.tools.result import ToolExecutionResult

_OTHER_OPTION = {
    "label": "Other",
    "description": "Type your own answer",
}


def _require_session(session):
    if session is None:
        raise ValueError("ask_user requires an active session")
    return session


class AskUserTool(ToolBase):
    def __init__(self, config, workdir):
        self.config = config
        self.workdir = Path(workdir)

    def exec(self, arguments: dict, session=None) -> ToolExecutionResult:
        session = _require_session(session)
        event = {
            "type": "question_asked",
            "session_id": session.session_id,
            "turn_id": getattr(session, "current_turn_id", ""),
            "questions": _augment_questions(arguments["questions"]),
        }
        session.events.append(event)
        _persist_events(session)
        _emit_live_event(event)

        answer_line = sys.stdin.readline()
        if answer_line == "":
            raise RuntimeError("ask_user input stream closed")

        try:
            answers = _parse_answers(answer_line)
        except ValueError as exc:
            return ToolExecutionResult(
                name="ask_user",
                display_command="ask_user",
                model_output=f"error: {exc}",
                output_text=f"error: {exc}",
                is_error=True,
            )

        event["answers"] = answers
        _persist_events(session)
        output_text = json.dumps(answers, sort_keys=True)
        return ToolExecutionResult(
            name="ask_user",
            display_command="ask_user",
            model_output=output_text,
            output_text=output_text,
        )

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "ask_user",
                "description": (
                    "Ask the user one or more multiple-choice questions. Each question "
                    "automatically includes an 'Other' option for a custom answer."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "questions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "question": {"type": "string"},
                                    "options": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "label": {"type": "string"},
                                                "description": {"type": "string"},
                                            },
                                            "required": ["label", "description"],
                                        },
                                    },
                                },
                                "required": ["question", "options"],
                            },
                        }
                    },
                    "required": ["questions"],
                },
            },
        }


def _augment_questions(questions: list[dict]) -> list[dict]:
    augmented = []
    for question in questions:
        options = [dict(option) for option in question["options"]]
        if not any(option.get("label") == _OTHER_OPTION["label"] for option in options):
            options.append(dict(_OTHER_OPTION))
        augmented.append(
            {
                "question": question["question"],
                "options": options,
            }
        )
    return augmented


def _emit_live_event(event: dict) -> None:
    sys.stdout.write(json.dumps(event) + "\n")
    sys.stdout.flush()


def _parse_answers(answer_line: str) -> dict[str, str]:
    try:
        payload = json.loads(answer_line)
    except json.JSONDecodeError as exc:
        raise ValueError("malformed ask_user answer payload") from exc
    answers = payload.get("answers")
    if not isinstance(answers, dict):
        raise ValueError("malformed ask_user answer payload")
    return {str(key): str(value) for key, value in answers.items()}


def _persist_events(session) -> None:
    events_path = Path(session.root) / "events.jsonl"
    events_path.parent.mkdir(parents=True, exist_ok=True)
    events_path.write_text(
        "".join(json.dumps(event) + "\n" for event in session.events)
    )
