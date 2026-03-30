from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import tomllib


CONTEXT_SETTING_KEYS = (
    "context_recent_turns",
    "context_working_token_budget",
    "context_max_tokens",
    "context_summary_max_tokens",
)


@dataclass(frozen=True)
class ProjectRecord:
    path: Path
    name: str
    key: str
    state_dir: Path
    last_opened_at: str


class ProjectRegistry:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.config_path = self.root / "config.toml"
        self.projects_dir = self.root / "projects"

    def default_model(self) -> str | None:
        return self._load().get("default_model")

    def set_default_model(self, model_name: str) -> None:
        data = self._load()
        data["default_model"] = model_name
        self._save(data)

    def context_settings(self) -> dict[str, int]:
        data = self._load()
        return {
            key: data[key]
            for key in CONTEXT_SETTING_KEYS
            if key in data
        }

    def set_context_settings(self, settings: dict[str, int]) -> None:
        data = self._load()
        for key in CONTEXT_SETTING_KEYS:
            if key in settings:
                data[key] = int(settings[key])
        self._save(data)

    def open_workspace(self, workspace: Path) -> ProjectRecord:
        workspace = Path(workspace).resolve()
        data = self._load()
        record = self._find_existing(data, workspace) or self._new_record(workspace)
        data["current_project"] = str(workspace)
        data["projects"] = [
            project for project in data["projects"] if project["path"] != str(workspace)
        ] + [self._dump_record(record)]
        self._save(data)
        return record

    def current_project(self) -> ProjectRecord | None:
        data = self._load()
        current = data.get("current_project")
        if not current:
            return None
        return self._find_existing(data, Path(current))

    def _load(self) -> dict:
        if not self.config_path.exists():
            return {"projects": []}
        raw = tomllib.loads(self.config_path.read_text())
        data = {"projects": []}

        current_project = raw.get("current_project")
        if isinstance(current_project, str):
            data["current_project"] = current_project
        default_model = raw.get("default_model")
        if isinstance(default_model, str):
            data["default_model"] = default_model
        for key in CONTEXT_SETTING_KEYS:
            value = raw.get(key)
            if value is not None:
                data[key] = int(value)

        web_search = raw.get("web_search")
        if isinstance(web_search, dict):
            data["web_search"] = web_search

        for project in raw.get("projects", []):
            data["projects"].append(
                {
                    "path": str(project["path"]),
                    "name": str(project["name"]),
                    "key": str(project["key"]),
                    "last_opened_at": str(project["last_opened_at"]),
                }
            )

        return data

    def _save(self, data: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.projects_dir.mkdir(parents=True, exist_ok=True)

        lines = []
        current_project = data.get("current_project")
        if current_project:
            lines.append(f'current_project = "{self._escape(current_project)}"')
        default_model = data.get("default_model")
        if default_model:
            lines.append(f'default_model = "{self._escape(default_model)}"')
        for key in CONTEXT_SETTING_KEYS:
            value = data.get(key)
            if value is not None:
                lines.append(f"{key} = {int(value)}")

        web_search = data.get("web_search")
        if isinstance(web_search, dict) and web_search:
            _append_table(lines, "web_search", web_search)

        for project in data.get("projects", []):
            lines.extend(
                [
                    "",
                    "[[projects]]",
                    f'path = "{self._escape(project["path"])}"',
                    f'name = "{self._escape(project["name"])}"',
                    f'key = "{self._escape(project["key"])}"',
                    f'last_opened_at = "{self._escape(project["last_opened_at"])}"',
                ]
            )

        self.config_path.write_text("\n".join(lines) + "\n")

    def _find_existing(self, data: dict, workspace: Path) -> ProjectRecord | None:
        workspace = Path(workspace).resolve()
        for project in data.get("projects", []):
            if Path(project["path"]).resolve() == workspace:
                return self._load_record(project)
        return None

    def _new_record(self, workspace: Path) -> ProjectRecord:
        name = workspace.name or "workspace"
        digest = hashlib.sha1(str(workspace).encode("utf-8")).hexdigest()[:8]
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "workspace"
        key = f"{slug}-{digest}"
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        if now.endswith("+00:00"):
            now = f"{now[:-6]}Z"
        state_dir = self.projects_dir / key
        state_dir.mkdir(parents=True, exist_ok=True)
        return ProjectRecord(
            path=workspace,
            name=name,
            key=key,
            state_dir=state_dir,
            last_opened_at=now,
        )

    def _load_record(self, data: dict) -> ProjectRecord:
        path = Path(data["path"]).resolve()
        return ProjectRecord(
            path=path,
            name=data["name"],
            key=data["key"],
            state_dir=self.projects_dir / data["key"],
            last_opened_at=data["last_opened_at"],
        )

    def _dump_record(self, record: ProjectRecord) -> dict:
        return {
            "path": str(record.path),
            "name": record.name,
            "key": record.key,
            "last_opened_at": record.last_opened_at,
        }

    @staticmethod
    def _escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    @staticmethod
    def _unescape(value: str) -> str:
        return value.replace('\\"', '"').replace("\\\\", "\\")


def _append_table(lines: list[str], table_name: str, values: dict) -> None:
    lines.extend(["", f"[{table_name}]"])
    for key, value in values.items():
        if isinstance(value, dict):
            continue
        lines.append(_format_toml_assignment(key, value))
    for key, value in values.items():
        if not isinstance(value, dict):
            continue
        lines.extend(["", f"[{table_name}.{key}]"])
        for subkey, subvalue in value.items():
            lines.append(_format_toml_assignment(subkey, subvalue))


def _format_toml_assignment(key: str, value) -> str:
    if isinstance(value, bool):
        rendered = "true" if value else "false"
    elif isinstance(value, int):
        rendered = str(value)
    else:
        rendered = f'"{ProjectRegistry._escape(str(value))}"'
    return f"{key} = {rendered}"
