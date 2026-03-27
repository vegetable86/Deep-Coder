import json

from deep_coder.tools.base import ToolBase
from deep_coder.tools.result import ToolExecutionResult


def _require_session(session):
    if session is None:
        raise ValueError("history tools require an active session")
    return session


class HistoryLoadTool(ToolBase):
    def __init__(self, config, workdir):
        self.config = config
        self.workdir = workdir

    def exec(self, arguments: dict, session=None) -> ToolExecutionResult:
        session = _require_session(session)
        evidence_by_artifact = {
            evidence.get("artifact_id"): evidence for evidence in session.evidence
        }
        lines = []
        for artifact_id in arguments["artifact_ids"]:
            artifact = session.artifacts.get(artifact_id)
            if artifact is None:
                lines.append(f"Artifact {artifact_id}: not found")
                continue
            evidence = evidence_by_artifact.get(artifact_id, {})
            lines.append(
                "Artifact "
                f"{artifact_id}: "
                f"{json.dumps({'artifact': artifact, 'evidence': evidence}, sort_keys=True)}"
            )
        text = "\n".join(lines) if lines else "No artifact ids requested"
        return ToolExecutionResult(
            name="load_history_artifacts",
            display_command="load_history_artifacts",
            model_output=text,
            output_text=text,
        )

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "load_history_artifacts",
                "description": "Load exact stored history artifacts by id.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "artifact_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["artifact_ids"],
                },
            },
        }
