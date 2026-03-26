from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re


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
        data = {"projects": []}
        current_project = None
        default_model = None
        project = None

        for raw_line in self.config_path.read_text().splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line == "[[projects]]":
                project = {}
                data["projects"].append(project)
                continue

            key, _, raw_value = line.partition("=")
            key = key.strip()
            value = self._unescape(raw_value.strip().strip('"'))
            if project is not None:
                project[key] = value
            elif key == "current_project":
                current_project = value
            elif key == "default_model":
                default_model = value

        if current_project:
            data["current_project"] = current_project
        if default_model:
            data["default_model"] = default_model
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
