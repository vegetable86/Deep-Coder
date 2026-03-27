import pytest
from pathlib import Path
from deep_coder.skills.registry import SkillRegistry
from deep_coder.skills.models import SkillDefinition


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


def test_skill_registry_loads_skill_by_name(tmp_path):
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

    skill = registry.load_skill("python-tests")

    assert skill.name == "python-tests"
    assert skill.title == "Python Test Fixing"
    assert skill.summary == "Use when diagnosing pytest failures."
    assert skill.body == "Skill body.\n"


def test_skill_registry_ignores_non_markdown_files(tmp_path):
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
    (skills_root / "notes.txt").write_text("Not a skill file")
    (skills_root / "other.py").write_text("# Not a skill")

    registry = SkillRegistry(root=skills_root)

    skills = registry.list_skills()

    assert len(skills) == 1
    assert skills[0].name == "python-tests"


def test_skill_registry_handles_missing_skill(tmp_path):
    skills_root = tmp_path / ".deepcode" / "skills"
    skills_root.mkdir(parents=True)
    registry = SkillRegistry(root=skills_root)

    with pytest.raises(FileNotFoundError):
        registry.load_skill("nonexistent")


def test_skill_registry_parses_tags(tmp_path):
    skills_root = tmp_path / ".deepcode" / "skills"
    skills_root.mkdir(parents=True)
    (skills_root / "python-tests.md").write_text(
        "---\n"
        "name: python-tests\n"
        "title: Python Test Fixing\n"
        "summary: Use when diagnosing pytest failures.\n"
        "tags: [python, testing, pytest]\n"
        "---\n\n"
        "Skill body.\n"
    )

    registry = SkillRegistry(root=skills_root)

    skill = registry.load_skill("python-tests")

    assert skill.tags == ("python", "testing", "pytest")


def test_skill_registry_handles_empty_tags(tmp_path):
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

    skill = registry.load_skill("python-tests")

    assert skill.tags == ()