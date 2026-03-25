from abc import ABC, abstractmethod


class HarnessBase(ABC):
    @abstractmethod
    def __init__(self, config, model, prompt, context, tools):
        raise NotImplementedError

    @abstractmethod
    def run(self, session_locator, user_input: str):
        raise NotImplementedError

