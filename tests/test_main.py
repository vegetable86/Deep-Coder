from deep_coder.main import build_runtime
from deep_coder.projects.registry import ProjectRecord


def test_build_runtime_returns_expected_components(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    runtime = build_runtime(workdir=tmp_path, state_dir=tmp_path / ".deepcode")

    assert runtime["config"].workdir == tmp_path
    assert runtime["model"].manifest()["provider"] == "deepseek"
    assert runtime["prompt"].manifest()["name"] == "deepcoder"
    assert runtime["context"].strategy.manifest()["name"] == "simple_history"
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
