from deep_coder.config import RuntimeConfig


def test_runtime_config_has_deepseek_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    config = RuntimeConfig.from_env(workdir=tmp_path)

    assert config.model_provider == "deepseek"
    assert config.model_name == "deepseek-chat"
    assert config.state_dir.name == ".deepcode"


def test_runtime_config_exposes_layered_context_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    config = RuntimeConfig.from_env(workdir=tmp_path)

    assert config.context_recent_turns == 3
    assert config.context_working_token_budget > 0
    assert config.context_compact_threshold < config.context_working_token_budget


def test_runtime_config_uses_global_skills_root(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    config = RuntimeConfig.from_env(workdir=tmp_path, state_dir=tmp_path / ".deepcode")

    assert config.skills_dir == tmp_path / ".deepcode" / "skills"
