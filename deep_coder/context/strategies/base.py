from abc import ABC, abstractmethod


class ContextStrategyBase(ABC):
    def prepare_messages(self, session, system_prompt: str, user_input: str, skill_index: str = "", active_skill_bodies: str = "") -> list[dict]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if skill_index:
            messages.append({"role": "system", "content": skill_index})
        if active_skill_bodies:
            messages.append({"role": "system", "content": active_skill_bodies})
        messages.extend(self.build_working_set(session, system_prompt, user_input))
        return messages

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
