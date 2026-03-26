import uuid

from deep_coder.harness.base import HarnessBase
from deep_coder.harness.events import NullHarnessEventSink
from deep_coder.harness.result import HarnessResult


class DeepCoderHarness(HarnessBase):
    def __init__(self, config, model, prompt, context, tools):
        self.config = config
        self.model = model
        self.prompt = prompt
        self.context = context
        self.tools = tools

    def _publish(self, session, event_sink, event: dict) -> None:
        session.events.append(event)
        event_sink.emit(event)

    def _event(self, session, turn_id: str, event_type: str, **payload) -> dict:
        return {
            "type": event_type,
            "session_id": session.session_id,
            "turn_id": turn_id,
            **payload,
        }

    def run(self, session_locator, user_input: str, event_sink=None):
        session = self.context.open(locator=session_locator)
        event_sink = event_sink or NullHarnessEventSink()
        tool_results = []
        current_input = user_input
        turn_id = uuid.uuid4().hex[:12]

        self._publish(
            session,
            event_sink,
            self._event(session, turn_id, "turn_started"),
        )

        while True:
            system_prompt = self.prompt.render(
                session_snapshot=session.meta(),
                tool_schemas=self.tools.schemas(),
            )
            messages = self.context.prepare_messages(session, system_prompt, current_input)
            if current_input is not None:
                self.context.record_event(session, {"role": "user", "content": current_input})
                self._publish(
                    session,
                    event_sink,
                    self._event(
                        session,
                        turn_id,
                        "message_committed",
                        role="user",
                        text=current_input,
                    ),
                )
                current_input = None
            response = self.model.complete({"messages": messages, "tools": self.tools.schemas()})

            if response["usage"]:
                self._publish(
                    session,
                    event_sink,
                    self._event(session, turn_id, "usage_reported", **response["usage"]),
                )

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
                    output = self.tools.execute(
                        tool_call["name"],
                        tool_call["arguments"],
                        session=session,
                    )
                    tool_results.append(output)
                    self._publish(
                        session,
                        event_sink,
                        self._event(
                            session,
                            turn_id,
                            "tool_called",
                            tool_call_id=tool_call["id"],
                            name=tool_call["name"],
                            display_command=output.display_command,
                            arguments=tool_call["arguments"],
                        ),
                    )
                    self.context.record_event(
                        session,
                        {
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": output.model_output,
                        },
                    )
                    self._publish(
                        session,
                        event_sink,
                        self._event(
                            session,
                            turn_id,
                            "tool_output",
                            tool_call_id=tool_call["id"],
                            name=tool_call["name"],
                            output_text=output.output_text,
                            is_error=output.is_error,
                        ),
                    )
                    if output.diff_text:
                        self._publish(
                            session,
                            event_sink,
                            self._event(
                                session,
                                turn_id,
                                "tool_diff",
                                tool_call_id=tool_call["id"],
                                name=tool_call["name"],
                                path=tool_call["arguments"].get("path"),
                                diff_text=output.diff_text,
                            ),
                        )
                    for extra_event in output.timeline_events:
                        self._publish(
                            session,
                            event_sink,
                            self._event(
                                session,
                                turn_id,
                                extra_event["type"],
                                **extra_event["payload"],
                            ),
                        )
                self.context.flush(session)
                continue

            assistant_text = response["content"] or ""
            self.context.record_event(
                session,
                {"role": "assistant", "content": assistant_text},
            )
            self._publish(
                session,
                event_sink,
                self._event(
                    session,
                    turn_id,
                    "message_committed",
                    role="assistant",
                    text=assistant_text,
                ),
            )
            self._publish(
                session,
                event_sink,
                self._event(
                    session,
                    turn_id,
                    "turn_finished",
                    finish_reason=response["finish_reason"],
                ),
            )
            self.context.flush(session)
            return HarnessResult(
                final_text=assistant_text,
                tool_results=tool_results,
                session_id=session.session_id,
            )
