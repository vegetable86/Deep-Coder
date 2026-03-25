from deep_coder.config import RuntimeConfig
from deep_coder.prompts.deepcoder.prompt import DeepCoderPrompt


def test_prompt_render_mentions_workdir_and_tool_names(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    config = RuntimeConfig.from_env(workdir=tmp_path, state_dir=tmp_path / ".deepcode")
    prompt = DeepCoderPrompt(config=config)

    text = prompt.render(
        session_snapshot={"id": "session-1"},
        tool_schemas=[
            {"function": {"name": "bash"}},
            {"function": {"name": "read_file"}},
        ],
    )

    assert str(config.workdir) in text
    assert "bash" in text
    assert "read_file" in text


def test_prompt_manifest_identifies_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    config = RuntimeConfig.from_env(workdir=tmp_path, state_dir=tmp_path / ".deepcode")
    prompt = DeepCoderPrompt(config=config)

    assert prompt.manifest() == {"name": "deepcoder"}
