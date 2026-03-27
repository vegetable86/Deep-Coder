import yaml
from pathlib import Path
from typing import List
from .models import SkillDefinition


class SkillRegistry:
    def __init__(self, root: Path):
        self.root = root

    def list_skills(self) -> List[SkillDefinition]:
        skills = []
        if not self.root.exists():
            return skills

        for path in self.root.glob("*.md"):
            try:
                skill = self._load_skill_from_path(path)
                skills.append(skill)
            except Exception:
                continue

        return sorted(skills, key=lambda s: s.name)

    def load_skill(self, name: str) -> SkillDefinition:
        path = self.root / f"{name}.md"
        if not path.exists():
            raise FileNotFoundError(f"Skill '{name}' not found at {path}")
        return self._load_skill_from_path(path)

    def _load_skill_from_path(self, path: Path) -> SkillDefinition:
        content = path.read_text(encoding="utf-8")
        if not content.startswith("---\n"):
            raise ValueError(f"Skill file {path} does not start with YAML frontmatter")

        parts = content.split("---\n", 2)
        if len(parts) < 3:
            raise ValueError(f"Skill file {path} has malformed YAML frontmatter")

        frontmatter = yaml.safe_load(parts[1])
        body = parts[2].lstrip('\n')

        name = frontmatter.get("name")
        title = frontmatter.get("title")
        summary = frontmatter.get("summary")

        if not name or not title or not summary:
            raise ValueError(f"Skill file {path} missing required fields: name, title, summary")

        tags = frontmatter.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]

        return SkillDefinition(
            name=name,
            title=title,
            summary=summary,
            body=body,
            path=path,
            tags=tuple(tags),
        )