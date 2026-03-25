from deep_coder.config import RuntimeConfig


def main() -> RuntimeConfig:
    return RuntimeConfig.from_env()

