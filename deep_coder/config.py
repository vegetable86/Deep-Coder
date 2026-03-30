from dataclasses import dataclass
import os
from pathlib import Path
import tomllib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from deep_coder.tools.web_search.providers.base import SearchProvider


DEFAULT_CONTEXT_SETTINGS = {
    "context_recent_turns": 3,
    "context_working_token_budget": 6000,
    "context_max_tokens": 128000,
    "context_summary_max_tokens": 1200,
    "context_reasoning_max_chars": 4000,
}


@dataclass
class RuntimeConfig:
    model_provider: str
    model_name: str
    api_key: str
    base_url: str
    workdir: Path
    state_dir: Path
    global_state_dir: Path
    project_path: Path
    project_key: str
    project_name: str
    context_recent_turns: int
    context_working_token_budget: int
    context_max_tokens: int
    context_summary_max_tokens: int
    context_reasoning_max_chars: int
    web_search_settings: dict | None = None
    web_search_provider: "SearchProvider | None" = None

    @property
    def skills_dir(self) -> Path:
        return self.global_state_dir / "skills"

    @classmethod
    def from_env(
        cls,
        workdir: Path | None = None,
        state_dir: Path | None = None,
        global_state_dir: Path | None = None,
        model_name: str | None = None,
        context_settings: dict | None = None,
    ):
        workdir = (workdir or Path.cwd()).resolve()
        state_dir = Path(state_dir or (Path.home() / ".deepcode")).resolve()
        global_state_dir = Path(global_state_dir or state_dir).resolve()
        context_values = _resolve_context_settings(context_settings)
        return cls(
            model_provider="deepseek",
            model_name=model_name or "deepseek-chat",
            api_key=os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com",
            workdir=workdir,
            state_dir=state_dir,
            global_state_dir=global_state_dir,
            project_path=workdir,
            project_key="default",
            project_name=workdir.name or "workspace",
            context_recent_turns=context_values["context_recent_turns"],
            context_working_token_budget=context_values["context_working_token_budget"],
            context_max_tokens=context_values["context_max_tokens"],
            context_summary_max_tokens=context_values["context_summary_max_tokens"],
            context_reasoning_max_chars=context_values["context_reasoning_max_chars"],
            web_search_settings=load_web_search_settings(global_state_dir),
        )

    @classmethod
    def from_project(
        cls,
        project,
        global_state_dir: Path | None = None,
        model_name: str | None = None,
        context_settings: dict | None = None,
    ):
        global_state_dir = (global_state_dir or (Path.home() / ".deepcode")).resolve()
        context_values = _resolve_context_settings(context_settings)
        return cls(
            model_provider="deepseek",
            model_name=model_name or "deepseek-chat",
            api_key=os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com",
            workdir=project.path,
            state_dir=project.state_dir,
            global_state_dir=global_state_dir,
            project_path=project.path,
            project_key=project.key,
            project_name=project.name,
            context_recent_turns=context_values["context_recent_turns"],
            context_working_token_budget=context_values["context_working_token_budget"],
            context_max_tokens=context_values["context_max_tokens"],
            context_summary_max_tokens=context_values["context_summary_max_tokens"],
            context_reasoning_max_chars=context_values["context_reasoning_max_chars"],
            web_search_settings=load_web_search_settings(global_state_dir),
        )


def _resolve_context_settings(context_settings: dict | None) -> dict[str, int]:
    values = dict(DEFAULT_CONTEXT_SETTINGS)
    if not context_settings:
        return values
    for key in DEFAULT_CONTEXT_SETTINGS:
        if key in context_settings and context_settings[key] is not None:
            values[key] = int(context_settings[key])
    return values


def load_web_search_settings(global_state_dir: Path) -> dict | None:
    config_path = Path(global_state_dir) / "config.toml"
    if not config_path.exists():
        return None
    data = tomllib.loads(config_path.read_text())
    settings = data.get("web_search")
    if not isinstance(settings, dict) or not settings:
        return None
    return settings
