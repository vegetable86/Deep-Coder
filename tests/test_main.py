from deep_coder.main import build_runtime


def test_build_runtime_returns_expected_components(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    runtime = build_runtime(workdir=tmp_path, state_dir=tmp_path / ".deepcode")

    assert runtime["config"].workdir == tmp_path
    assert runtime["model"].manifest()["provider"] == "deepseek"
    assert runtime["prompt"].manifest()["name"] == "deepcoder"
    assert runtime["context"].strategy.manifest()["name"] == "simple_history"
    assert runtime["tools"].schemas()
