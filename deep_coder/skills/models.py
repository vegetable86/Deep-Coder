from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SkillDefinition:
    name: str
    title: str
    summary: str
    body: str
    path: Path
    tags: tuple[str, ...] = ()