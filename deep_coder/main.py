from pathlib import Path

from deep_coder.config import RuntimeConfig
from deep_coder.context.manager import ContextManager
from deep_coder.context.summarizers.model import ModelSummarizer
from deep_coder.context.stores.filesystem.store import FileSystemSessionStore
from deep_coder.context.strategies.layered_history.strategy import (
    LayeredHistoryContextStrategy,
)
from deep_coder.harness.deepcoder.harness import DeepCoderHarness
from deep_coder.models.deepseek.model import DeepSeekModel
from deep_coder.prompts.deepcoder.prompt import DeepCoderPrompt
from deep_coder.projects.registry import ProjectRecord
from deep_coder.tools.registry import ToolRegistry


def build_runtime(
    workdir: Path | None = None,
    state_dir: Path | None = None,
    global_state_dir: Path | None = None,
    project: ProjectRecord | None = None,
    model_name: str | None = None,
    context_settings: dict | None = None,
    registry=None,
) -> dict:
    if project is not None:
        config = RuntimeConfig.from_project(
            project,
            global_state_dir=global_state_dir,
            model_name=model_name,
            context_settings=context_settings,
        )
    else:
        config = RuntimeConfig.from_env(
            workdir=workdir,
            state_dir=state_dir,
            global_state_dir=global_state_dir,
            model_name=model_name,
            context_settings=context_settings,
        )
    model = DeepSeekModel(config=config)
    tools = ToolRegistry.from_builtin(config=config, workdir=config.workdir)
    prompt = DeepCoderPrompt(config=config)
    context = ContextManager(
        store=FileSystemSessionStore(
            root=config.state_dir,
            project_key=config.project_key,
            workspace_path=config.project_path,
        ),
        strategy=LayeredHistoryContextStrategy(
            config=config,
            summarizer=ModelSummarizer(model=model, config=config),
        ),
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
        "registry": registry,
    }


def main() -> dict:
    return build_runtime()
