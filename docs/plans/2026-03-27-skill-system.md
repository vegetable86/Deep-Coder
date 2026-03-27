# Skill System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a global skill system to Deep Coder with a model-visible skill index, dynamic model and user activation, session-scoped active skills, and compaction-safe prompt injection from `~/.deepcode/skills/`.

**Architecture:** Introduce a dedicated `deep_coder/skills/` subsystem that discovers and parses global skill files, extend session metadata to track active skills, add a skill-loading tool plus `/skills` commands, and update prompt assembly so the base prompt, skill index, and active skill bodies are injected above compacted conversation history. Keep the harness thin and preserve the existing boundaries between TUI commands, prompt generation, context management, and tool execution.

**Tech Stack:** Python 3, Textual, Rich, pytest, stdlib filesystem APIs, existing Deep Coder runtime modules

**Execution Notes:** Follow `@test-driven-development` and `@verification-before-completion` throughout. If request assembly or session persistence behavior becomes unclear, stop and use `@systematic-debugging`.

---

### Task 1: Add the global skill registry and skill file parsing

**Files:**
- Create: `deep_coder/skills/__init__.py`
- Create: `deep_coder/skills/models.py`
- Create: `deep_coder/skills/registry.py`
- Modify: `deep_coder/config.py`
- Test: `tests/skills/test_registry.py`
- Test: `tests/test_config.py`

**Step 1: Write the failing tests**

```python
def test_skill_registry_lists_skill_metadata(tmp_path):
    skills_root = tmp_path / ".deepcode" / "skills"
    skills_root.mkdir(parents=True)
    (skills_root / "python-tests.md").write_text(
        "---\n"
        "name: python-tests\n"
        "title: Python Test Fixing\n"
        "summary: Use when diagnosing pytest failures.\n"
        "---\n\n"
        "Skill body.\n"
    )

    registry = SkillRegistry(root=skills_root)

    skills = registry.list_skills()

    assert [skill.name for skill in skills] == ["python-tests"]
    assert skills[0].title == "Python Test Fixing"
```

```python
def test_runtime_config_uses_global_skills_root(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    config = RuntimeConfig.from_env(workdir=tmp_path, state_dir=tmp_path / ".deepcode")

    assert config.skills_dir == tmp_path / ".deepcode" / "skills"
```

**Step 2: Run tests to verify they fail**

Run: `/home/wys/deep-code/.venv/bin/pytest tests/skills/test_registry.py tests/test_config.py -q`
Expected: FAIL because the skill registry does not exist and runtime config does not expose a skills root

**Step 3: Write the minimal implementation**

```python
@dataclass(frozen=True)
class SkillDefinition:
    name: str
    title: str
    summary: str
    body: str
    path: Path
    tags: tuple[str, ...] = ()
```

```python
class SkillRegistry:
    def list_skills(self) -> list[SkillDefinition]:
        ...

    def load_skill(self, name: str) -> SkillDefinition:
        ...
```

**Step 4: Run tests to verify they pass**

Run: `/home/wys/deep-code/.venv/bin/pytest tests/skills/test_registry.py tests/test_config.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add deep_coder/skills/__init__.py deep_coder/skills/models.py deep_coder/skills/registry.py deep_coder/config.py tests/skills/test_registry.py tests/test_config.py
git commit -m "feat: add global skill registry"
```

### Task 2: Persist session-active skills in session metadata

**Files:**
- Modify: `deep_coder/context/session.py`
- Modify: `deep_coder/context/stores/filesystem/store.py`
- Test: `tests/context/test_filesystem_store.py`

**Step 1: Write the failing tests**

```python
def test_session_meta_includes_active_skills(tmp_path):
    session = Session(
        session_id="session-1",
        root=tmp_path,
        active_skills=[
            {
                "name": "python-tests",
                "title": "Python Test Fixing",
                "hash": "sha256:test",
                "activated_at": "2026-03-27T00:00:00Z",
                "source": "user",
            }
        ],
    )

    assert session.meta()["active_skills"][0]["name"] == "python-tests"
```

```python
def test_filesystem_store_round_trips_active_skills(tmp_path):
    store = FileSystemSessionStore(root=tmp_path)
    session = store.open(locator={"id": "session-a"})
    session.active_skills = [
        {
            "name": "python-tests",
            "title": "Python Test Fixing",
            "hash": "sha256:test",
            "activated_at": "2026-03-27T00:00:00Z",
            "source": "model",
        }
    ]

    store.save(session)
    reloaded = store.open(locator={"id": "session-a"})

    assert reloaded.active_skills[0]["source"] == "model"
```

**Step 2: Run tests to verify they fail**

Run: `/home/wys/deep-code/.venv/bin/pytest tests/context/test_filesystem_store.py -q`
Expected: FAIL because sessions do not yet store active skill metadata

**Step 3: Write the minimal implementation**

```python
@dataclass
class Session:
    ...
    active_skills: list[dict] = field(default_factory=list)
```

```python
def meta(self) -> dict:
    meta = {...}
    if self.active_skills:
        meta["active_skills"] = self.active_skills
    return meta
```

**Step 4: Run tests to verify they pass**

Run: `/home/wys/deep-code/.venv/bin/pytest tests/context/test_filesystem_store.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add deep_coder/context/session.py deep_coder/context/stores/filesystem/store.py tests/context/test_filesystem_store.py
git commit -m "feat: persist session active skills"
```

### Task 3: Add skill-aware message assembly and compaction-safe prompt injection

**Files:**
- Modify: `deep_coder/prompts/deepcoder/prompt.py`
- Modify: `deep_coder/context/manager.py`
- Modify: `deep_coder/main.py`
- Modify: `deep_coder/harness/deepcoder/harness.py`
- Test: `tests/prompts/test_deepcoder_prompt.py`
- Test: `tests/context/test_layered_context_manager.py`
- Test: `tests/harness/test_deepcoder_harness.py`

**Step 1: Write the failing tests**

```python
def test_prompt_renders_skill_index(config):
    prompt = DeepCoderPrompt(config=config)

    text = prompt.render(
        session_snapshot={"id": "session-a"},
        tool_schemas=[],
        skill_index=[
            {
                "name": "python-tests",
                "title": "Python Test Fixing",
                "summary": "Use when diagnosing pytest failures.",
            }
        ],
    )

    assert "python-tests" in text
    assert "load_skill" in text
```

```python
def test_prepare_messages_injects_active_skills_before_history(fake_session, context_manager):
    fake_session.active_skills = [
        {"name": "python-tests", "title": "Python Test Fixing", "hash": "sha256:test", "source": "user"}
    ]

    messages = context_manager.prepare_messages(
        fake_session,
        system_prompt="base",
        user_input="Fix the tests",
        active_skill_messages=[{"role": "system", "content": "Skill body"}],
    )

    assert messages[0]["content"] == "base"
    assert messages[1]["content"] == "Skill body"
```

**Step 2: Run tests to verify they fail**

Run: `/home/wys/deep-code/.venv/bin/pytest tests/prompts/test_deepcoder_prompt.py tests/context/test_layered_context_manager.py tests/harness/test_deepcoder_harness.py -q`
Expected: FAIL because prompts and message assembly do not yet support skill index or active skill overlays

**Step 3: Write the minimal implementation**

```python
def render(self, session_snapshot: dict, tool_schemas: list[dict], skill_index: list[dict]) -> str:
    ...
```

```python
def prepare_messages(self, session, system_prompt: str, user_input: str, active_skill_messages: list[dict] | None = None) -> list[dict]:
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(active_skill_messages or [])
    messages.extend(self.strategy.build_working_set(session, system_prompt, user_input))
    messages.append({"role": "user", "content": user_input})
    return messages
```

**Step 4: Run tests to verify they pass**

Run: `/home/wys/deep-code/.venv/bin/pytest tests/prompts/test_deepcoder_prompt.py tests/context/test_layered_context_manager.py tests/harness/test_deepcoder_harness.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add deep_coder/prompts/deepcoder/prompt.py deep_coder/context/manager.py deep_coder/main.py deep_coder/harness/deepcoder/harness.py tests/prompts/test_deepcoder_prompt.py tests/context/test_layered_context_manager.py tests/harness/test_deepcoder_harness.py
git commit -m "feat: inject skills into runtime prompts"
```

### Task 4: Add the model skill-loading tool and runtime activation flow

**Files:**
- Create: `deep_coder/tools/skills/tool.py`
- Modify: `deep_coder/tools/registry.py`
- Modify: `deep_coder/context/manager.py`
- Modify: `deep_coder/harness/deepcoder/harness.py`
- Test: `tests/tools/test_skill_tool.py`
- Test: `tests/harness/test_deepcoder_harness.py`

**Step 1: Write the failing tests**

```python
def test_load_skill_tool_returns_skill_body_and_metadata(skill_registry, session):
    tool = LoadSkillTool(config=fake_config, workdir=fake_config.workdir, skills=skill_registry)

    result = tool.exec({"name": "python-tests"}, session=session)

    assert result.output_text.startswith("Skill loaded:")
    assert "Python Test Fixing" in result.model_output
```

```python
def test_harness_marks_loaded_skill_active(fake_runtime, fake_session, fake_model_response):
    ...
    assert fake_session.active_skills[0]["name"] == "python-tests"
```

**Step 2: Run tests to verify they fail**

Run: `/home/wys/deep-code/.venv/bin/pytest tests/tools/test_skill_tool.py tests/harness/test_deepcoder_harness.py -q`
Expected: FAIL because no skill-loading tool exists

**Step 3: Write the minimal implementation**

```python
class LoadSkillTool(ToolBase):
    def exec(self, arguments: dict, session=None) -> ToolExecutionResult:
        skill = self.skills.load_skill(arguments["name"])
        ...
```

```python
context.activate_skill(
    session,
    name=skill.name,
    title=skill.title,
    hash=skill.hash,
    source="model",
)
```

**Step 4: Run tests to verify they pass**

Run: `/home/wys/deep-code/.venv/bin/pytest tests/tools/test_skill_tool.py tests/harness/test_deepcoder_harness.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add deep_coder/tools/skills/tool.py deep_coder/tools/registry.py deep_coder/context/manager.py deep_coder/harness/deepcoder/harness.py tests/tools/test_skill_tool.py tests/harness/test_deepcoder_harness.py
git commit -m "feat: add dynamic skill loading tool"
```

### Task 5: Add `/skills` commands and command-palette completions

**Files:**
- Create: `deep_coder/tui/commands/builtin/skills.py`
- Modify: `deep_coder/tui/commands/base.py`
- Modify: `deep_coder/tui/commands/registry.py`
- Modify: `deep_coder/tui/commands/builtin/__init__.py`
- Modify: `deep_coder/tui/app.py`
- Test: `tests/tui/test_commands.py`
- Test: `tests/tui/test_app_layout.py`

**Step 1: Write the failing tests**

```python
def test_skills_command_lists_global_skills(fake_runtime, fake_project):
    registry = CommandRegistry.with_builtin_commands()

    result = registry.execute(
        "/skills",
        runtime=fake_runtime,
        project=fake_project,
        session_id="session-a",
        turn_state="idle",
    )

    assert result.list_kind == "skills"
    assert result.list_items[0]["name"] == "python-tests"
```

```python
def test_skills_use_command_activates_skill(fake_runtime, fake_project):
    registry = CommandRegistry.with_builtin_commands()

    result = registry.execute(
        "/skills use python-tests",
        runtime=fake_runtime,
        project=fake_project,
        session_id="session-a",
        turn_state="idle",
    )

    assert result.status_message == "skill active: python-tests"
```

**Step 2: Run tests to verify they fail**

Run: `/home/wys/deep-code/.venv/bin/pytest tests/tui/test_commands.py tests/tui/test_app_layout.py -q`
Expected: FAIL because `/skills` commands and completions do not exist

**Step 3: Write the minimal implementation**

```python
class SkillsCommand(CommandBase):
    name = "skills"
    summary = "List and manage session skills"
```

```python
def complete(self, context: CommandContext, args: str) -> list[CommandMatch] | None:
    ...
```

**Step 4: Run tests to verify they pass**

Run: `/home/wys/deep-code/.venv/bin/pytest tests/tui/test_commands.py tests/tui/test_app_layout.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add deep_coder/tui/commands/builtin/skills.py deep_coder/tui/commands/base.py deep_coder/tui/commands/registry.py deep_coder/tui/commands/builtin/__init__.py deep_coder/tui/app.py tests/tui/test_commands.py tests/tui/test_app_layout.py
git commit -m "feat: add session skill commands"
```

### Task 6: Add replay events, failure handling, and end-to-end verification

**Files:**
- Modify: `deep_coder/tui/render.py`
- Modify: `deep_coder/tui/app.py`
- Modify: `deep_coder/context/manager.py`
- Modify: `deep_coder/harness/deepcoder/harness.py`
- Test: `tests/tui/test_live_events.py`
- Test: `tests/harness/test_turn_subprocess.py`
- Test: `tests/context/test_layered_history_strategy.py`

**Step 1: Write the failing tests**

```python
def test_skill_activation_event_renders_in_timeline():
    event = {
        "type": "skill_activated",
        "name": "python-tests",
        "title": "Python Test Fixing",
        "source": "model",
    }

    block = render_skill_event_block(event)

    assert "python-tests" in str(block)
```

```python
def test_missing_active_skill_emits_warning_event(...):
    ...
    assert any(event["type"] == "skill_missing" for event in session.events)
```

**Step 2: Run tests to verify they fail**

Run: `/home/wys/deep-code/.venv/bin/pytest tests/tui/test_live_events.py tests/harness/test_turn_subprocess.py tests/context/test_layered_history_strategy.py -q`
Expected: FAIL because skill replay events and missing-skill handling do not exist

**Step 3: Write the minimal implementation**

```python
if event_type in {"skill_loaded", "skill_activated", "skill_dropped", "skill_missing"}:
    block = render_skill_event_block(event)
```

```python
if not skill_path.exists():
    emit({"type": "skill_missing", ...})
```

**Step 4: Run tests to verify they pass**

Run: `/home/wys/deep-code/.venv/bin/pytest tests/tui/test_live_events.py tests/harness/test_turn_subprocess.py tests/context/test_layered_history_strategy.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add deep_coder/tui/render.py deep_coder/tui/app.py deep_coder/context/manager.py deep_coder/harness/deepcoder/harness.py tests/tui/test_live_events.py tests/harness/test_turn_subprocess.py tests/context/test_layered_history_strategy.py
git commit -m "feat: add skill replay events"
```

### Task 7: Run full verification and update docs if behavior changed during implementation

**Files:**
- Modify: `README.md` if command usage or storage paths need documentation
- Modify: `arch/arch.md` if the final module split differs from this design

**Step 1: Run the full test suite**

Run: `/home/wys/deep-code/.venv/bin/pytest -q`
Expected: PASS

**Step 2: Manually smoke-test the TUI skill flow**

Run: `DEEPSEEK_API_KEY=test-key ./deepcode`
Expected:
- `/skills` lists discovered skills
- `/skills use <name>` marks the skill active
- an active skill remains applied across later turns
- compaction does not remove active skill overlays

**Step 3: Update documentation if needed**

```md
- Add a short `Skills` section describing `~/.deepcode/skills/`
- Document `/skills` commands
```

**Step 4: Re-run the full test suite**

Run: `/home/wys/deep-code/.venv/bin/pytest -q`
Expected: PASS

**Step 5: Commit**

```bash
git add README.md arch/arch.md
git commit -m "docs: update skill system documentation"
```
