from deep_coder.context.strategies.base import ContextStrategyBase


class SimpleHistoryContextStrategy(ContextStrategyBase):
    def prepare_messages(self, session, system_prompt: str, user_input: str) -> list[dict]:
        messages = [
            {"role": "system", "content": system_prompt},
            *session.messages,
        ]
        if user_input is not None:
            messages.append({"role": "user", "content": user_input})
        return messages

    def record_event(self, session, event: dict) -> None:
        session.append(event)

    def maybe_compact(self, session, usage: dict | None = None) -> None:
        return None

    @staticmethod
    def manifest() -> dict:
        return {"name": "simple_history"}
