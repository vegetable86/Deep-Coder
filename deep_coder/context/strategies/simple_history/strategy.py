from deep_coder.context.strategies.base import ContextStrategyBase


class SimpleHistoryContextStrategy(ContextStrategyBase):
    def prepare_messages(self, session, system_prompt: str, user_input: str) -> list[dict]:
        return [
            {"role": "system", "content": system_prompt},
            *session.messages,
            {"role": "user", "content": user_input},
        ]

    def record_event(self, session, event: dict) -> None:
        session.append(event)

    def maybe_compact(self, session, usage: dict | None = None) -> None:
        return None

    @staticmethod
    def manifest() -> dict:
        return {"name": "simple_history"}
