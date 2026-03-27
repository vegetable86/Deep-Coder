from dataclasses import dataclass
import hashlib
from pathlib import Path


@dataclass(frozen=True)
class SkillDefinition:
    name: str
    title: str
    summary: str
    body: str
    path: Path
    tags: tuple[str, ...] = ()

    @property
    def content_hash(self) -> str:
        digest = hashlib.sha256(self.body.encode("utf-8")).hexdigest()
        return f"sha256:{digest}"
