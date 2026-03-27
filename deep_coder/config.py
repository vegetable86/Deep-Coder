from dataclasses import dataclass
import os
from pathlib import Path


@dataclass
class RuntimeConfig:
    model_provider: str
    model_name: str
    api_key: str
    base_url: str
    workdir: Path
    state_dir: Path
    project_path: Path
    project_key: str
    project_name: str
    context_recent_turns: int
    context_working_token_budget: int
    context_compact_threshold: int
    context_summary_max_tokens: int

    @classmethod
    def from_env(
        cls,
        workdir: Path | None = None,
        state_dir: Path | None = None,
        model_name: str | None = None,
    ):
        workdir = (workdir or Path.cwd()).resolve()
        state_dir = state_dir or (Path.home() / ".deepcode")
        return cls(
            model_provider="deepseek",
            model_name=model_name or "deepseek-chat",
            api_key=os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com",
            workdir=workdir,
            state_dir=state_dir,
            project_path=workdir,
            project_key="default",
            project_name=workdir.name or "workspace",
            context_recent_turns=3,
            context_working_token_budget=6000,
            context_compact_threshold=4500,
            context_summary_max_tokens=1200,
        )

    @classmethod
    def from_project(cls, project, model_name: str | None = None):
        return cls(
            model_provider="deepseek",
            model_name=model_name or "deepseek-chat",
            api_key=os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com",
            workdir=project.path,
            state_dir=project.state_dir,
            project_path=project.path,
            project_key=project.key,
            project_name=project.name,
            context_recent_turns=3,
            context_working_token_budget=6000,
            context_compact_threshold=4500,
            context_summary_max_tokens=1200,
        )
