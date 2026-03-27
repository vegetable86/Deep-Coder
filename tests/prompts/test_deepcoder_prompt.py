from deep_coder.config import RuntimeConfig
from deep_coder.prompts.deepcoder.prompt import DeepCoderPrompt


def test_prompt_render_includes_role_and_session_context(tmp_path, monkeypatch):
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

    assert "You are DeepCode, a project-scoped coding agent" in text
    assert str(config.workdir) in text
    assert "Current session: session-1" in text
    assert "bash" in text
    assert "read_file" in text


def test_prompt_render_prefers_summary_first_history_recall(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    config = RuntimeConfig.from_env(workdir=tmp_path, state_dir=tmp_path / ".deepcode")
    prompt = DeepCoderPrompt(config=config)

    text = prompt.render(
        session_snapshot={"id": "session-1"},
        tool_schemas=[
            {"function": {"name": "search_history"}},
            {"function": {"name": "load_history_artifacts"}},
        ],
    )

    assert "Prefer summary first." in text
    assert "Only load original history artifacts" in text


def test_prompt_render_requires_brief_intent_before_action(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    config = RuntimeConfig.from_env(workdir=tmp_path, state_dir=tmp_path / ".deepcode")
    prompt = DeepCoderPrompt(config=config)

    text = prompt.render(
        session_snapshot={"id": "session-1"},
        tool_schemas=[{"function": {"name": "read_file"}}],
    )

    assert "Before taking a non-trivial action" in text
    assert "briefly state your intent" in text


def test_prompt_render_guides_model_to_load_skills_when_available(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    config = RuntimeConfig.from_env(workdir=tmp_path, state_dir=tmp_path / ".deepcode")
    prompt = DeepCoderPrompt(config=config)

    text = prompt.render(
        session_snapshot={"id": "session-1"},
        tool_schemas=[
            {"function": {"name": "read_file"}},
            {"function": {"name": "load_skill"}},
        ],
    )

    assert "skill" in text.lower()
    assert "load_skill" in text


def test_prompt_manifest_identifies_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    config = RuntimeConfig.from_env(workdir=tmp_path, state_dir=tmp_path / ".deepcode")
    prompt = DeepCoderPrompt(config=config)

    assert prompt.manifest() == {"name": "deepcoder"}
