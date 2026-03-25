from deep_coder.harness.base import HarnessBase
from deep_coder.harness.result import HarnessResult


class DeepCoderHarness(HarnessBase):
    def __init__(self, config, model, prompt, context, tools):
        self.config = config
        self.model = model
        self.prompt = prompt
        self.context = context
        self.tools = tools

    def run(self, session_locator, user_input: str):
        session = self.context.open(locator=session_locator)
        tool_results = []
        current_input = user_input
        user_recorded = False

        while True:
            system_prompt = self.prompt.render(
                session_snapshot=session.meta(),
                tool_schemas=self.tools.schemas(),
            )
            messages = self.context.prepare_messages(session, system_prompt, current_input)
            response = self.model.complete({"messages": messages, "tools": self.tools.schemas()})

            if not user_recorded:
                self.context.record_event(session, {"role": "user", "content": user_input})
                user_recorded = True
                current_input = None

            if response["tool_calls"]:
                self.context.record_event(
                    session,
                    {
                        "role": "assistant",
                        "content": response["content"] or "",
                        "tool_calls": response["tool_calls"],
                    },
                )
                for tool_call in response["tool_calls"]:
                    output = self.tools.execute(tool_call["name"], tool_call["arguments"])
                    tool_results.append(output)
                    self.context.record_event(
                        session,
                        {
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": output,
                        },
                    )
                self.context.flush(session)
                continue

            self.context.record_event(
                session,
                {"role": "assistant", "content": response["content"] or ""},
            )
            self.context.flush(session)
            return HarnessResult(
                final_text=response["content"] or "",
                tool_results=tool_results,
                session_id=session.session_id,
            )
