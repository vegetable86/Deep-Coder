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
    assert config.context_max_tokens == 128000
    assert config.context_max_tokens > config.context_working_token_budget


def test_runtime_config_uses_global_skills_root(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    config = RuntimeConfig.from_env(workdir=tmp_path, state_dir=tmp_path / ".deepcode")

    assert config.skills_dir == tmp_path / ".deepcode" / "skills"


def test_runtime_config_reads_web_search_settings_from_global_config(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    state_dir = tmp_path / ".deepcode"
    state_dir.mkdir()
    (state_dir / "config.toml").write_text(
        "\n".join(
            [
                '[web_search]',
                'provider = "google"',
                "",
                "[web_search.google]",
                'api_key = "google-key"',
                'cx = "search-cx"',
                "",
            ]
        )
    )

    config = RuntimeConfig.from_env(workdir=tmp_path, state_dir=state_dir)

    assert config.web_search_settings == {
        "provider": "google",
        "google": {"api_key": "google-key", "cx": "search-cx"},
    }
    assert config.web_search_provider is None


def test_runtime_config_defaults_web_search_settings_to_none(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    config = RuntimeConfig.from_env(workdir=tmp_path, state_dir=tmp_path / ".deepcode")

    assert config.web_search_settings is None
    assert config.web_search_provider is None
