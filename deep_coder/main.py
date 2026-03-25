from pathlib import Path

from deep_coder.config import RuntimeConfig
from deep_coder.context.manager import ContextManager
from deep_coder.context.stores.filesystem.store import FileSystemSessionStore
from deep_coder.context.strategies.simple_history.strategy import (
    SimpleHistoryContextStrategy,
)
from deep_coder.harness.deepcoder.harness import DeepCoderHarness
from deep_coder.models.deepseek.model import DeepSeekModel
from deep_coder.prompts.deepcoder.prompt import DeepCoderPrompt
from deep_coder.projects.registry import ProjectRecord
from deep_coder.tools.registry import ToolRegistry


def build_runtime(
    workdir: Path | None = None,
    state_dir: Path | None = None,
    project: ProjectRecord | None = None,
) -> dict:
    if project is not None:
        config = RuntimeConfig.from_project(project)
    else:
        config = RuntimeConfig.from_env(workdir=workdir, state_dir=state_dir)
    model = DeepSeekModel(config=config)
    tools = ToolRegistry.from_builtin(config=config, workdir=config.workdir)
    prompt = DeepCoderPrompt(config=config)
    context = ContextManager(
        store=FileSystemSessionStore(
            root=config.state_dir,
            project_key=config.project_key,
            workspace_path=config.project_path,
        ),
        strategy=SimpleHistoryContextStrategy(),
    )
    harness = DeepCoderHarness(
        config=config,
        model=model,
        prompt=prompt,
        context=context,
        tools=tools,
    )
    return {
        "config": config,
        "model": model,
        "tools": tools,
        "prompt": prompt,
        "context": context,
        "harness": harness,
    }


def main() -> dict:
    return build_runtime()
