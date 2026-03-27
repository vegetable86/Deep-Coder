import pytest
from pathlib import Path
import os
from deep_coder.config import RuntimeConfig


def test_runtime_config_uses_global_skills_root(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    config = RuntimeConfig.from_env(workdir=tmp_path, state_dir=tmp_path / ".deepcode")

    assert config.skills_dir == tmp_path / ".deepcode" / "skills"