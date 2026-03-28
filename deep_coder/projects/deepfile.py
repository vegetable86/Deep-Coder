from dataclasses import dataclass
from pathlib import Path
import fnmatch


PRIORITY_PATTERNS = (
    "DEEP.md",
    "README*",
    "CONTRIBUTING*",
    "docs/**",
    "arch/**",
    "pyproject.toml",
    "package.json",
    "pytest.ini",
    "Makefile",
)
IGNORE_DIR_NAMES = {".git", "node_modules", ".venv", "venv", "dist", "build", ".next"}


@dataclass(frozen=True)
class DeepFileSource:
    relative_path: str
    category: str


@dataclass(frozen=True)
class DiscoveryResult:
    sources: list[DeepFileSource]


def _is_priority_match(relative_path: str) -> bool:
    for pattern in PRIORITY_PATTERNS:
        if fnmatch.fnmatch(relative_path, pattern):
            return True
    return False


def _category(relative_path: str) -> str:
    if relative_path == "DEEP.md":
        return "deep"
    elif relative_path.startswith("README"):
        return "readme"
    elif relative_path.startswith("CONTRIBUTING"):
        return "contributing"
    elif relative_path.startswith("docs/"):
        return "docs"
    elif relative_path.startswith("arch/"):
        return "arch"
    elif relative_path in ("pyproject.toml", "package.json", "pytest.ini", "Makefile"):
        return "config"
    else:
        return "other"


def _priority_key(relative_path: str) -> int:
    if relative_path == "DEEP.md":
        return 0
    elif relative_path.startswith("README"):
        return 1
    elif relative_path.startswith("CONTRIBUTING"):
        return 2
    elif relative_path.startswith("docs/"):
        return 3
    elif relative_path.startswith("arch/"):
        return 4
    elif relative_path in ("pyproject.toml", "package.json", "pytest.ini", "Makefile"):
        return 5
    else:
        return 6


class DeepFileService:
    def __init__(self, *, workspace: Path, state_dir: Path):
        self.workspace = Path(workspace).resolve()
        self.state_dir = Path(state_dir)

    def discover_sources(self) -> DiscoveryResult:
        discovered: list[DeepFileSource] = []
        for path in sorted(self.workspace.rglob("*")):
            if path.is_dir() and path.name in IGNORE_DIR_NAMES:
                continue
            if not path.is_file():
                continue
            rel = path.relative_to(self.workspace).as_posix()
            if _is_priority_match(rel):
                discovered.append(DeepFileSource(relative_path=rel, category=_category(rel)))
        discovered.sort(key=lambda source: _priority_key(source.relative_path))
        return DiscoveryResult(sources=discovered)