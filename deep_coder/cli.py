from pathlib import Path

from deep_coder.main import build_runtime
from deep_coder.projects.registry import ProjectRegistry
from deep_coder.tui.app import DeepCodeApp


def resolve_launch_context(
    cwd: Path | None = None,
    registry_root: Path | None = None,
):
    cwd = (cwd or Path.cwd()).resolve()
    registry = ProjectRegistry(root=registry_root or (Path.home() / ".deepcode"))
    project = registry.open_workspace(cwd)
    runtime = build_runtime(
        project=project,
        model_name=registry.default_model(),
        registry=registry,
    )
    return project, runtime


def main() -> int:
    project, runtime = resolve_launch_context()
    DeepCodeApp(runtime=runtime, project=project).run(mouse=False)
    return 0
