from deep_coder.context.stores.base import SessionStoreBase
from deep_coder.context.strategies.base import ContextStrategyBase


class ContextManager:
    def __init__(self, store: SessionStoreBase, strategy: ContextStrategyBase):
        self.store = store
        self.strategy = strategy

    def list_sessions(self) -> list[dict]:
        return self.store.list_sessions()

    def open(self, locator: dict | None = None):
        return self.store.open(locator=locator)

    def prepare_messages(self, session, system_prompt: str, user_input: str) -> list[dict]:
        return self.strategy.prepare_messages(session, system_prompt, user_input)

    def record_event(self, session, event: dict) -> None:
        self.strategy.record_event(session, event)

    def flush(self, session) -> None:
        self.store.save(session)

