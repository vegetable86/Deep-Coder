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


def test_prompt_render_includes_cli_preamble_and_security_scope(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    config = RuntimeConfig.from_env(workdir=tmp_path, state_dir=tmp_path / ".deepcode")
    prompt = DeepCoderPrompt(config=config)

    text = prompt.render(
        session_snapshot={"id": "session-1"},
        tool_schemas=[{"function": {"name": "bash"}}],
    )

    assert "You are an interactive CLI tool that helps users with software engineering tasks." in text
    assert "Assist with defensive security tasks only." in text


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


def test_prompt_render_checks_context_sufficiency_before_history_lookup(
    tmp_path, monkeypatch
):
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

    assert "If the current message and visible context are enough" in text
    assert "answer directly without retrieval" in text


def test_prompt_render_searches_compact_history_before_loading_evidence(
    tmp_path, monkeypatch
):
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

    assert "use search_history to search compact session history first" in text
    assert "Use concrete anchors such as files, functions, errors, decisions, constraints, or task subjects" in text
    assert "Use load_history_artifacts only when compact history is insufficient" in text
    assert "exact wording, tool arguments, outputs, diffs, or evidence matter" in text


def test_prompt_render_uses_task_tools_only_for_multi_step_work(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    config = RuntimeConfig.from_env(workdir=tmp_path, state_dir=tmp_path / ".deepcode")
    prompt = DeepCoderPrompt(config=config)

    text = prompt.render(
        session_snapshot={"id": "session-1"},
        tool_schemas=[
            {"function": {"name": "task_create"}},
            {"function": {"name": "task_update"}},
        ],
    )

    assert "Use task tools for multi-step work" in text
    assert "Do not create or update tasks for one-shot answers" in text


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
