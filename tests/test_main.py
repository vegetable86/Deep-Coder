from deep_coder.main import build_runtime
from deep_coder.projects.registry import ProjectRecord


def test_build_runtime_returns_expected_components(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    runtime = build_runtime(workdir=tmp_path, state_dir=tmp_path / ".deepcode")

    assert runtime["config"].workdir == tmp_path
    assert runtime["model"].manifest()["provider"] == "deepseek"
    assert runtime["prompt"].manifest()["name"] == "deepcoder"
    assert runtime["context"].strategy.manifest()["name"] == "layered_history"
    assert runtime["context"].strategy.summarizer.model is runtime["model"]
    assert runtime["tools"].schemas()


def test_build_runtime_uses_project_state_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    workspace = tmp_path / "repo"
    workspace.mkdir()
    project = ProjectRecord(
        path=workspace,
        name="repo",
        key="repo-abc123",
        state_dir=tmp_path / ".deepcode" / "projects" / "repo-abc123",
        last_opened_at="2026-03-25T00:00:00Z",
    )

    runtime = build_runtime(project=project)

    assert runtime["config"].project_key == "repo-abc123"
    assert runtime["config"].state_dir == project.state_dir


def test_build_runtime_uses_explicit_model_name(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    workspace = tmp_path / "repo"
    workspace.mkdir()
    project = ProjectRecord(
        path=workspace,
        name="repo",
        key="repo-abc123",
        state_dir=tmp_path / ".deepcode" / "projects" / "repo-abc123",
        last_opened_at="2026-03-26T00:00:00Z",
    )

    runtime = build_runtime(project=project, model_name="deepseek-reasoner")

    assert runtime["config"].model_name == "deepseek-reasoner"


def test_build_runtime_builds_web_search_provider_from_global_config(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    state_dir = tmp_path / ".deepcode"
    state_dir.mkdir()
    (state_dir / "config.toml").write_text(
        "\n".join(
            [
                '[web_search]',
                'provider = "serper"',
                "",
                "[web_search.serper]",
                'api_key = "serper-key"',
                "",
            ]
        )
    )

    runtime = build_runtime(workdir=tmp_path, state_dir=state_dir)

    assert runtime["config"].web_search_provider is not None
    assert runtime["config"].web_search_provider.__class__.__name__ == "SerperProvider"
    names = [schema["function"]["name"] for schema in runtime["tools"].schemas()]
    assert "web_search" in names
