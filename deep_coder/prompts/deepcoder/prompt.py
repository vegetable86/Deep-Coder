from deep_coder.prompts.base import PromptBase


class DeepCoderPrompt(PromptBase):
    def __init__(self, config):
        self.config = config

    def render(self, session_snapshot: dict, tool_schemas: list[dict]) -> str:
        tool_names = ", ".join(schema["function"]["name"] for schema in tool_schemas)
        session_id = session_snapshot.get("id", "new-session")
        return (
            f"You are Deep Coder working in {self.config.workdir}. "
            f"Current session: {session_id}. "
            f"Available tools: {tool_names}."
        )

    @staticmethod
    def manifest() -> dict:
        return {"name": "deepcoder"}
