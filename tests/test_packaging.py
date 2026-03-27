import re
from pathlib import Path


def _read_pyproject() -> str:
    return Path("pyproject.toml").read_text(encoding="utf-8")


def test_pyproject_declares_deepcode_console_script():
    text = _read_pyproject()

    assert '[project.scripts]' in text
    assert 'deepcode = "deep_coder.cli:main"' in text


def test_pyproject_declares_runtime_and_dev_dependencies():
    text = _read_pyproject()

    assert re.search(r'(?m)^dependencies\s*=\s*\[', text)
    assert re.search(r'(?m)^dev\s*=\s*\[', text)
    assert re.search(r'"openai[^"]*"', text)
    assert re.search(r'"rich[^"]*"', text)
    assert re.search(r'"textual[^"]*"', text)
    assert re.search(r'"pytest[^"]*"', text)


def test_readme_uses_mermaid_and_documents_source_install_and_commands():
    text = Path("README.md").read_text(encoding="utf-8")

    assert text.startswith("# Deep Coder")
    assert "```mermaid" in text
    assert "python3 -m pip install --user ." in text
    assert 'python3 -m pip install -e ".[dev]"' in text
    assert "`deepcode`" in text
    assert "/history" in text
    assert "/session" in text
    assert "/model" in text
    assert "Ctrl+L" in text
    assert "Ctrl+C" in text
