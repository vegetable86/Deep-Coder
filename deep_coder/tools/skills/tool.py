import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

from deep_coder.tools.base import ToolBase
from deep_coder.skills.registry import SkillRegistry


class SkillLoadTool(ToolBase):
    def __init__(self, config, workdir):
        self.config = config
        self.workdir = workdir
        self.registry = SkillRegistry(root=config.skills_dir)

    def exec(self, arguments: dict, session=None) -> dict[str, Any]:
        name = arguments["name"]
        source = arguments.get("source", "model")

        try:
            skill = self.registry.load_skill(name)
        except FileNotFoundError:
            return {
                "success": False,
                "error": f"Skill '{name}' not found in {self.config.skills_dir}",
            }

        # Compute hash of skill body
        body_hash = hashlib.sha256(skill.body.encode("utf-8")).hexdigest()
        skill_hash = f"sha256:{body_hash}"

        # Check if already active
        if session and session.active_skills:
            for active in session.active_skills:
                if active["name"] == name and active["hash"] == skill_hash:
                    return {
                        "success": True,
                        "message": f"Skill '{name}' is already active",
                        "skill": {
                            "name": skill.name,
                            "title": skill.title,
                            "summary": skill.summary,
                            "hash": skill_hash,
                        },
                    }

        # Add to session active skills
        skill_record = {
            "name": skill.name,
            "title": skill.title,
            "hash": skill_hash,
            "activated_at": datetime.utcnow().isoformat() + "Z",
            "source": source,
        }

        if session:
            session.active_skills.append(skill_record)

        return {
            "success": True,
            "message": f"Skill '{name}' loaded and activated",
            "skill": {
                "name": skill.name,
                "title": skill.title,
                "summary": skill.summary,
                "hash": skill_hash,
                "body": skill.body,
            },
        }

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