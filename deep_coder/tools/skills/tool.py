from datetime import datetime, timezone

from deep_coder.tools.base import ToolBase
from deep_coder.tools.result import ToolExecutionResult
from deep_coder.skills.registry import SkillRegistry


class SkillLoadTool(ToolBase):
    def __init__(self, config, workdir):
        self.config = config
        self.workdir = workdir
        self.registry = SkillRegistry(root=config.skills_dir)

    def exec(self, arguments: dict, session=None) -> ToolExecutionResult:
        name = arguments["name"]
        source = arguments.get("source", "model")

        try:
            skill = self.registry.load_skill(name)
        except FileNotFoundError:
            error = f"error: skill '{name}' not found in {self.config.skills_dir}"
            return ToolExecutionResult(
                name="load_skill",
                display_command="load_skill",
                model_output=error,
                output_text=error,
                is_error=True,
            )

        was_active = False
        if session is not None:
            for active_skill in session.active_skills:
                if active_skill["name"] == skill.name and active_skill["hash"] == skill.content_hash:
                    was_active = True
                    break

        if session is not None and not was_active:
            session.active_skills = [
                active_skill
                for active_skill in session.active_skills
                if active_skill["name"] != skill.name
            ]
            session.active_skills.append(
                {
                    "name": skill.name,
                    "title": skill.title,
                    "hash": skill.content_hash,
                    "activated_at": _utc_now(),
                    "source": source,
                }
            )

        model_output = "\n".join(
            [
                f"Skill loaded: {skill.name}",
                f"Title: {skill.title}",
                f"Summary: {skill.summary}",
                "",
                skill.body,
            ]
        )
        output_text = f"skill active: {skill.name}"
        timeline_events = []
        if not was_active:
            timeline_events.append(
                {
                    "type": "skill_activated",
                    "payload": {
                        "name": skill.name,
                        "title": skill.title,
                        "source": source,
                        "hash": skill.content_hash,
                    },
                }
            )

        return ToolExecutionResult(
            name="load_skill",
            display_command="load_skill",
            model_output=model_output,
            output_text=output_text,
            timeline_events=timeline_events,
        )

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "load_skill",
                "description": "Load a skill from the global skill registry and activate it for the current session.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name of the skill (filename without .md extension)",
                        },
                        "source": {
                            "type": "string",
                            "enum": ["model", "user"],
                            "description": "Who activated the skill (default: model)",
                            "default": "model",
                        },
                    },
                    "required": ["name"],
                },
            },
        }


def _utc_now() -> str:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return now.replace("+00:00", "Z")
