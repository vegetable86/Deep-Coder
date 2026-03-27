from abc import ABC, abstractmethod


class ContextStrategyBase(ABC):
    def prepare_messages(self, session, system_prompt: str, user_input: str) -> list[dict]:
        return [
            {"role": "system", "content": system_prompt},
            *self.build_working_set(session, system_prompt, user_input),
        ]

    @abstractmethod
    def build_working_set(
        self,
        session,
        system_prompt: str,
        user_input: str | None,
    ) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def record_event(self, session, event: dict) -> None:
        raise NotImplementedError

    @abstractmethod
    def should_compact(self, session, usage: dict | None = None) -> bool:
        raise NotImplementedError

    @abstractmethod
    def maybe_compact(self, session, usage: dict | None = None) -> bool:
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def manifest() -> dict:
        raise NotImplementedError
