from pathlib import Path

from .models import SkillDefinition


class SkillRegistry:
    def __init__(self, root: Path):
        self.root = Path(root)

    def list_skills(self) -> list[SkillDefinition]:
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
        frontmatter, body = _parse_frontmatter(content, path)

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


def _parse_frontmatter(content: str, path: Path) -> tuple[dict[str, object], str]:
    if not content.startswith("---\n"):
        raise ValueError(f"Skill file {path} does not start with YAML frontmatter")

    try:
        _, remainder = content.split("---\n", 1)
        frontmatter_text, body = remainder.split("\n---\n", 1)
    except ValueError as exc:
        raise ValueError(f"Skill file {path} has malformed YAML frontmatter") from exc

    metadata: dict[str, object] = {}
    for raw_line in frontmatter_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        key, separator, raw_value = line.partition(":")
        if not separator:
            raise ValueError(f"Skill file {path} has malformed frontmatter line: {raw_line}")
        metadata[key.strip()] = _parse_metadata_value(raw_value.strip())
    return metadata, body.lstrip("\n")


def _parse_metadata_value(value: str) -> object:
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip("'\"") for item in inner.split(",") if item.strip()]
    return value.strip().strip("'\"")
