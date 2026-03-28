from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re


PRIORITY_PATTERNS = (
    "README*",
    "CONTRIBUTING*",
    "docs/**",
    "arch/**",
    "AGENTS.md",
    "pyproject.toml",
    "package.json",
    "pytest.ini",
    "Makefile",
    "requirements.txt",
)
IGNORE_DIR_NAMES = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    ".next",
    "__pycache__",
    ".pytest_cache",
}
TEXT_EXTENSIONS = {
    "",
    ".cfg",
    ".ini",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
TEXT_SOURCE_MAX_BYTES = 128_000
LEGACY_KEYWORDS = ("legacy", "prototype", "deprecated", "reference file", "not the main entrypoint")
STATE_KEYWORDS = ("state under", "lives under", "persisted state under", "runtime state under")
AUTHORITATIVE_KEYWORDS = ("authoritative", "current product", "source of truth")
DEFAULT_HUMAN_NOTES = (
    "Add your project-specific notes, conventions, and reminders below.\n"
    "This section is preserved across `/init` refreshes."
)
SPECIAL_EDIT_HINTS = {
    "api": "server or API surface",
    "app": "application shell or route entrypoints",
    "components": "reusable UI components",
    "context": "session and context persistence",
    "harness": "runtime orchestration",
    "models": "model/provider adapters",
    "pages": "page-level entrypoints",
    "projects": "workspace and project registry logic",
    "tools": "tool schemas and local execution logic",
    "tui": "terminal UI and slash-command flow",
}

START_MARKER = "<!-- deepcode:init:start -->"
END_MARKER = "<!-- deepcode:init:end -->"


@dataclass(frozen=True)
class DeepFileSource:
    relative_path: str
    category: str
    text: str | None = None


@dataclass(frozen=True)
class DiscoveryResult:
    sources: list[DeepFileSource]


@dataclass(frozen=True)
class RefreshResult:
    changed: bool
    source_paths: list[str]
    deep_file_path: Path


def _is_priority_match(relative_path: str) -> bool:
    for pattern in PRIORITY_PATTERNS:
        if Path(relative_path).match(pattern):
            return True
    return False


def _category(relative_path: str) -> str:
    if relative_path == "AGENTS.md":
        return "instructions"
    if relative_path.startswith("README"):
        return "readme"
    if relative_path.startswith("CONTRIBUTING"):
        return "contributing"
    if relative_path.startswith("docs/"):
        return "docs"
    if relative_path.startswith("arch/"):
        return "arch"
    if relative_path in ("pyproject.toml", "package.json", "pytest.ini", "Makefile", "requirements.txt"):
        return "config"
    return "other"


def _priority_key(relative_path: str) -> tuple[int, str]:
    if relative_path.startswith("README"):
        return (0, relative_path)
    if relative_path.startswith("CONTRIBUTING"):
        return (1, relative_path)
    if relative_path.startswith("docs/"):
        return (2, relative_path)
    if relative_path.startswith("arch/"):
        return (3, relative_path)
    if relative_path == "AGENTS.md":
        return (4, relative_path)
    if relative_path in ("pyproject.toml", "package.json", "pytest.ini", "Makefile", "requirements.txt"):
        return (5, relative_path)
    return (6, relative_path)


def _read_source_text(path: Path) -> str | None:
    try:
        if path.suffix not in TEXT_EXTENSIONS or path.stat().st_size > TEXT_SOURCE_MAX_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _project_script_targets(pyproject_text: str | None) -> dict[str, str]:
    if not pyproject_text:
        return {}

    scripts: dict[str, str] = {}
    in_section = False
    for raw_line in pyproject_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            in_section = line == "[project.scripts]"
            continue
        if not in_section or "=" not in line:
            continue
        key, _, raw_value = line.partition("=")
        scripts[key.strip()] = raw_value.strip().strip('"').strip("'")
    return scripts


def _module_target_to_path(target: str) -> str | None:
    module_name = target.split(":", 1)[0].strip()
    if not module_name:
        return None
    return f"{module_name.replace('.', '/')}.py"


def _top_level_package_dirs(workspace: Path, pyproject_text: str | None) -> list[str]:
    package_dirs: list[str] = []

    for child in sorted(workspace.iterdir()):
        if not child.is_dir() or child.name in IGNORE_DIR_NAMES or child.name.startswith("."):
            continue
        if (child / "__init__.py").exists():
            package_dirs.append(f"{child.name}/")

    for target in _project_script_targets(pyproject_text).values():
        module_path = _module_target_to_path(target)
        if not module_path:
            continue
        top_level = module_path.split("/", 1)[0]
        candidate = workspace / top_level
        if candidate.is_dir() and (candidate / "__init__.py").exists():
            package_dirs.append(f"{top_level}/")

    return _unique(package_dirs)


def _root_launchers(workspace: Path, pyproject_text: str | None) -> list[str]:
    launchers: list[str] = []

    for script_name in _project_script_targets(pyproject_text):
        if (workspace / script_name).is_file():
            launchers.append(script_name)

    for child in sorted(workspace.iterdir()):
        if not child.is_file() or child.name.startswith(".") or child.suffix:
            continue
        text = _read_source_text(child) or ""
        if text.startswith("#!"):
            launchers.append(child.name)

    return _unique(launchers)


def _doc_lines(discovery: DiscoveryResult) -> list[str]:
    lines: list[str] = []
    for source in discovery.sources:
        if not source.text:
            continue
        lines.extend(source.text.splitlines())
    return lines


def _looks_like_path(value: str) -> bool:
    return "/" in value or value.endswith(".py") or value.endswith(".md") or value.startswith("~")


def _extract_document_paths(lines: list[str], keywords: tuple[str, ...]) -> list[str]:
    paths: list[str] = []
    for line in lines:
        lowered = line.lower()
        if not any(keyword in lowered for keyword in keywords):
            continue
        for match in re.findall(r"`([^`]+)`", line):
            if _looks_like_path(match):
                paths.append(match)
    return _unique(paths)


def _path_exists(workspace: Path, relative_path: str) -> bool:
    if relative_path.startswith("~"):
        return True
    return (workspace / relative_path.rstrip("/")).exists()


def _project_map_bullets(workspace: Path, discovery: DiscoveryResult) -> list[str]:
    source_map = {source.relative_path: source for source in discovery.sources}
    pyproject_text = source_map.get("pyproject.toml").text if "pyproject.toml" in source_map else None
    bullets: list[str] = []
    lines = _doc_lines(discovery)

    if "README.md" in source_map:
        bullets.append("`README.md`: overview, setup steps, and contributor-facing usage notes.")

    for path in _extract_document_paths(lines, AUTHORITATIVE_KEYWORDS):
        if _path_exists(workspace, path):
            bullets.append(f"`{path}`: authoritative implementation or active launch surface.")

    for launcher in _root_launchers(workspace, pyproject_text):
        bullets.append(f"`{launcher}`: checked-in launcher or command entrypoint.")

    for package_dir in _top_level_package_dirs(workspace, pyproject_text):
        bullets.append(f"`{package_dir}`: primary package or application code.")

    for path, description in (
        ("tests/", "automated regression coverage."),
        ("docs/", "project docs and plans."),
        ("arch/", "architecture notes and design references."),
    ):
        if (workspace / path.rstrip("/")).exists():
            bullets.append(f"`{path}`: {description}")

    return _unique(bullets)[:6]


def _start_here_bullets(workspace: Path, discovery: DiscoveryResult) -> list[str]:
    source_map = {source.relative_path: source for source in discovery.sources}
    pyproject_text = source_map.get("pyproject.toml").text if "pyproject.toml" in source_map else None
    bullets: list[str] = []

    for launcher in _root_launchers(workspace, pyproject_text):
        bullets.append(f"`{launcher}`: start the local launch flow here.")

    for script_name, target in _project_script_targets(pyproject_text).items():
        module_path = _module_target_to_path(target)
        if not module_path or not (workspace / module_path).exists():
            continue
        bullets.append(f"`{module_path}`: Python entrypoint behind `{script_name}`.")

    for package_dir in _top_level_package_dirs(workspace, pyproject_text):
        for candidate, description in (
            ("cli.py", "command bootstrap inside the main package."),
            ("main.py", "composition root or runtime bootstrap."),
            ("app.py", "application shell entrypoint."),
        ):
            relative_path = f"{package_dir}{candidate}"
            if (workspace / relative_path).is_file():
                bullets.append(f"`{relative_path}`: {description}")

    if "README.md" in source_map:
        bullets.append("`README.md`: product overview and setup context before editing.")
    if "AGENTS.md" in source_map:
        bullets.append("`AGENTS.md`: repo-specific operating constraints when present.")

    return _unique(bullets)[:5]


def _common_edit_bullets(workspace: Path, discovery: DiscoveryResult) -> list[str]:
    source_map = {source.relative_path: source for source in discovery.sources}
    pyproject_text = source_map.get("pyproject.toml").text if "pyproject.toml" in source_map else None
    bullets: list[str] = []

    for package_dir in _top_level_package_dirs(workspace, pyproject_text):
        package_path = workspace / package_dir.rstrip("/")
        specialized = False
        for subdir_name, description in SPECIAL_EDIT_HINTS.items():
            candidate = package_path / subdir_name
            if candidate.is_dir():
                bullets.append(f"`{package_dir}{subdir_name}/`: {description}")
                specialized = True
        if not specialized:
            bullets.append(f"`{package_dir}`: main application code for feature work and fixes.")

    if (workspace / "tests").is_dir():
        bullets.append("`tests/`: add or update regression coverage for behavior changes.")
    if (workspace / "docs").is_dir():
        bullets.append("`docs/`: contributor docs, plans, and supporting references.")
    if (workspace / "arch").is_dir():
        bullets.append("`arch/`: architecture notes when a change needs higher-level context.")

    return _unique(bullets)[:6]


def _verification_bullets(workspace: Path, discovery: DiscoveryResult) -> list[str]:
    source_map = {source.relative_path: source for source in discovery.sources}
    bullets: list[str] = []

    if (workspace / ".venv" / "bin" / "pytest").exists():
        bullets.append("`./.venv/bin/pytest -q`: repo-local pytest suite.")
    if "pytest.ini" in source_map or (workspace / "tests").is_dir():
        bullets.append("`python3 -m pytest -q`: primary Python test suite.")
    if "package.json" in source_map:
        bullets.append("`npm test`: package.json test script.")
    if (workspace / "Makefile").exists():
        bullets.append("`make test`: check whether the Makefile exposes repo verification.")

    return _unique(bullets)[:3]


def _boundaries_bullets(workspace: Path, discovery: DiscoveryResult) -> list[str]:
    bullets: list[str] = []
    lines = _doc_lines(discovery)

    for path in _extract_document_paths(lines, LEGACY_KEYWORDS):
        bullets.append(f"`{path}`: legacy or reference-only path; do not treat it as the active entrypoint.")
    for path in _extract_document_paths(lines, STATE_KEYWORDS):
        bullets.append(f"`{path}`: runtime state or config lives outside the normal edit surface.")

    ignored_present = [
        f"`{name}/`"
        for name in sorted(IGNORE_DIR_NAMES)
        if (workspace / name).exists()
    ]
    if ignored_present:
        bullets.append(
            f"Avoid dependency, cache, or generated trees unless the task is specifically about them: {', '.join(ignored_present)}."
        )

    return _unique(bullets)[:4]


def _render_section(title: str, bullets: list[str]) -> list[str]:
    if not bullets:
        return []
    lines = [f"## {title}", ""]
    lines.extend(f"- {bullet}" for bullet in bullets)
    lines.append("")
    return lines


def _render_generated_block(workspace: Path, discovery: DiscoveryResult) -> str:
    lines = [
        "# DEEP.md",
        "",
        "This file is generated by Deep Coder's `/init` command.",
        "Use it as a concise project editing guide for this workspace.",
        "",
    ]

    lines.extend(_render_section("Project Map", _project_map_bullets(workspace, discovery)))
    lines.extend(_render_section("Start Here", _start_here_bullets(workspace, discovery)))
    lines.extend(_render_section("Common Edits", _common_edit_bullets(workspace, discovery)))
    lines.extend(_render_section("Verification", _verification_bullets(workspace, discovery)))
    lines.extend(_render_section("Boundaries", _boundaries_bullets(workspace, discovery)))

    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def _clean_manual_notes_block(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""

    if cleaned.startswith("# DEEP.md"):
        cleaned = "\n".join(cleaned.splitlines()[1:]).strip()

    heading = "## Human Notes"
    if heading not in cleaned:
        return cleaned

    before, _, after = cleaned.partition(heading)
    parts = [part.strip() for part in (before, after) if part.strip()]
    return "\n\n".join(parts)


def _extract_manual_notes(existing_content: str) -> str:
    if not existing_content.strip():
        return DEFAULT_HUMAN_NOTES

    start_idx = existing_content.find(START_MARKER)
    end_idx = existing_content.find(END_MARKER)
    if start_idx != -1 and end_idx != -1:
        manual_area = existing_content[end_idx + len(END_MARKER) :]
    else:
        manual_area = existing_content

    manual_notes = _clean_manual_notes_block(manual_area)
    return manual_notes or DEFAULT_HUMAN_NOTES


def _compose_document(generated_block: str, manual_notes: str) -> str:
    notes = manual_notes.rstrip()
    return (
        f"{START_MARKER}\n"
        f"{generated_block}\n"
        f"{END_MARKER}\n\n"
        "## Human Notes\n\n"
        f"{notes}\n"
    )


def _merge_generated_block(existing_content: str, generated_block: str) -> str:
    return _compose_document(generated_block, _extract_manual_notes(existing_content))


class DeepFileService:
    def __init__(self, *, workspace: Path, state_dir: Path):
        self.workspace = Path(workspace).resolve()
        self.state_dir = Path(state_dir)

    def discover_sources(self) -> DiscoveryResult:
        discovered: list[DeepFileSource] = []
        for root, dirnames, filenames in os.walk(self.workspace, topdown=True):
            dirnames[:] = [
                dirname
                for dirname in sorted(dirnames)
                if dirname not in IGNORE_DIR_NAMES and not dirname.startswith(".")
            ]
            root_path = Path(root)
            for filename in sorted(filenames):
                relative_path = (root_path / filename).relative_to(self.workspace).as_posix()
                if not _is_priority_match(relative_path):
                    continue
                path = root_path / filename
                discovered.append(
                    DeepFileSource(
                        relative_path=relative_path,
                        category=_category(relative_path),
                        text=_read_source_text(path),
                    )
                )

        discovered.sort(key=lambda source: _priority_key(source.relative_path))
        return DiscoveryResult(sources=discovered)

    def refresh(self) -> RefreshResult:
        discovery = self.discover_sources()
        rendered_block = _render_generated_block(self.workspace, discovery)
        deep_file_path = self.workspace / "DEEP.md"
        existing = deep_file_path.read_text() if deep_file_path.exists() else ""
        updated = _merge_generated_block(existing, rendered_block)
        deep_file_path.write_text(updated)
        self._write_state(discovery.sources, deep_file_path)
        return RefreshResult(
            changed=updated != existing,
            source_paths=[source.relative_path for source in discovery.sources],
            deep_file_path=deep_file_path,
        )

    def _write_state(self, sources: list[DeepFileSource], deep_file_path: Path) -> None:
        state_path = self.state_dir / "deep" / "init-state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(
                {
                    "last_refreshed_at": datetime.now(timezone.utc).isoformat(),
                    "workspace_path": str(self.workspace),
                    "deep_file_path": str(deep_file_path),
                    "sources": [source.relative_path for source in sources],
                },
                indent=2,
            )
        )
