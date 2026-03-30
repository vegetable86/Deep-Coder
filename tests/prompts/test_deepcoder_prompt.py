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

    assert "If the user references something from a prior session" in text
    assert "call search_history before answering" in text
    assert "do not guess" in text


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

    assert "If the current task touches code or context you haven't seen in this turn" in text
    assert "call search_history to check whether prior work is relevant" in text
    assert "Only skip retrieval when the current message and visible context are fully sufficient" in text
    assert "Use concrete anchors such as files, functions, errors, decisions, constraints, or task subjects" in text
    assert "Use load_history_artifacts only when compact history is insufficient" in text
    assert "exact wording, tool arguments, outputs, diffs, or evidence matter" in text


def test_prompt_render_includes_think_and_web_search_trigger_rules(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    config = RuntimeConfig.from_env(workdir=tmp_path, state_dir=tmp_path / ".deepcode")
    prompt = DeepCoderPrompt(config=config)

    text = prompt.render(
        session_snapshot={"id": "session-1"},
        tool_schemas=[
            {"function": {"name": "think"}},
            {"function": {"name": "web_search"}},
        ],
    )

    assert "Before implementing any non-trivial feature, architectural change, or multi-step task, call think to plan your approach first." in text
    assert "When debugging a complex issue with multiple possible causes, call think to reason through them before acting." in text
    assert "When you need to evaluate trade-offs between approaches, call think before responding." in text
    assert "When you encounter an unfamiliar library, API, error message, or technology, call web_search before guessing." in text
    assert "When the user asks about something that may have changed since your training" in text
    assert "When official documentation would resolve ambiguity faster than reasoning from memory, call web_search." in text


def test_prompt_render_includes_proactive_clarification_triggers(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    config = RuntimeConfig.from_env(workdir=tmp_path, state_dir=tmp_path / ".deepcode")
    prompt = DeepCoderPrompt(config=config)

    text = prompt.render(
        session_snapshot={"id": "session-1"},
        tool_schemas=[{"function": {"name": "ask_user"}}],
    )

    assert "Be proactive only when the user asks you to do something." in text
    assert "If the user's request requires choosing between approaches and the choice meaningfully affects the outcome, call ask_user before acting." in text
    assert "If a task is ambiguous in a way that would cause you to make a significant assumption, call ask_user to resolve it first." in text
    assert "Do not ask for clarification on trivial details" in text


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
