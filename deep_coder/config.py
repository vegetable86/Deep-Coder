from dataclasses import dataclass
import os
from pathlib import Path


@dataclass
class RuntimeConfig:
    model_provider: str
    model_name: str
    api_key: str
    base_url: str
    workdir: Path
    state_dir: Path

    @classmethod
    def from_env(cls, workdir: Path | None = None):
        workdir = workdir or Path.cwd()
        return cls(
            model_provider="deepseek",
            model_name="deepseek-chat",
            api_key=os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com",
            workdir=workdir,
            state_dir=Path.home() / ".deepcode",
        )

