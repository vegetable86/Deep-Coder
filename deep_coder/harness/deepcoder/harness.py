import uuid

from deep_coder.harness.base import HarnessBase
from deep_coder.harness.events import NullHarnessEventSink
from deep_coder.harness.result import HarnessResult
from deep_coder.skills.registry import SkillRegistry
from deep_coder.tools.result import build_model_error_payload


class DeepCoderHarness(HarnessBase):
    def __init__(self, config, model, prompt, context, tools):
        self.config = config
        self.model = model
        self.prompt = prompt
        self.context = context
        self.tools = tools

    def _publish(self, session, event_sink, event: dict) -> None:
        session.events.append(event)
        self.context.flush(session)
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
        session.current_turn_id = turn_id

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
            skill_index, active_skill_bodies = self._skill_context(
                session,
                turn_id=turn_id,
                event_sink=event_sink,
            )

            messages = self.context.prepare_messages(
                session,
                system_prompt,
                current_input,
                skill_index,
                active_skill_bodies,
            )
            if current_input is not None:
                self.context.record_user_message(
                    session,
                    turn_id=turn_id,
                    text=current_input,
                )
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
            try:
                response = self.model.complete(
                    {"messages": messages, "tools": self.tools.schemas()}
                )
            except Exception as exc:
                self._publish(
                    session,
                    event_sink,
                    self._event(
                        session,
                        turn_id,
                        "model_error",
                        **build_model_error_payload(
                            self.config.model_name,
                            exc,
                            scope="main_model",
                        ),
                    ),
                )
                self._publish(
                    session,
                    event_sink,
                    self._event(
                        session,
                        turn_id,
                        "turn_failed",
                        reason="model_error",
                    ),
                )
                return HarnessResult(
                    final_text="",
                    tool_results=tool_results,
                    session_id=session.session_id,
                )

            if response["usage"]:
                self._publish(
                    session,
                    event_sink,
                    self._event(session, turn_id, "usage_reported", **response["usage"]),
                )
                if self.context.should_compact(session, usage=response["usage"]):
                    self._publish(
                        session,
                        event_sink,
                        self._event(session, turn_id, "context_compacting"),
                    )
                if self.context.maybe_compact(session, usage=response["usage"]):
                    self._publish(
                        session,
                        event_sink,
                        self._event(session, turn_id, "context_compacted"),
                    )

            if response["tool_calls"]:
                self.context.record_assistant_message(
                    session,
                    turn_id=turn_id,
                    text=response["content"] or "",
                    tool_calls=response["tool_calls"],
                )
                self.context.flush(session)
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
                    self.context.record_tool_result(
                        session,
                        turn_id=turn_id,
                        tool_call=tool_call,
                        output=output,
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
                    if output.reasoning_content:
                        self._publish(
                            session,
                            event_sink,
                            self._event(
                                session,
                                turn_id,
                                "reasoning_recorded",
                                tool_call_id=tool_call["id"],
                                name=tool_call["name"],
                                model_name=output.metadata.get(
                                    "model_name", "deepseek-reasoner"
                                ),
                                final_content=output.metadata.get("final_content", ""),
                                reasoning_content=output.reasoning_content,
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
                continue

            assistant_text = response["content"] or ""
            self.context.record_assistant_message(
                session,
                turn_id=turn_id,
                text=assistant_text,
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
            return HarnessResult(
                final_text=assistant_text,
                tool_results=tool_results,
                session_id=session.session_id,
            )

    def _skill_context(self, session, *, turn_id: str, event_sink) -> tuple[str, str]:
        if not hasattr(self.config, "skills_dir"):
            return "", ""

        registry = SkillRegistry(root=self.config.skills_dir)
        skill_index_lines = []
        skills = registry.list_skills()
        if skills:
            skill_index_lines.append("Available skills:")
            for skill in skills:
                skill_index_lines.append(f"- {skill.name}: {skill.title} - {skill.summary}")

        active_skill_bodies_lines = []
        for active_skill in session.active_skills:
            try:
                skill = registry.load_skill(active_skill["name"])
            except FileNotFoundError:
                self._publish(
                    session,
                    event_sink,
                    self._event(
                        session,
                        turn_id,
                        "skill_missing",
                        name=active_skill["name"],
                    ),
                )
                continue
            active_skill_bodies_lines.append(f"# Skill: {skill.title} ({skill.name})")
            active_skill_bodies_lines.append(skill.body)
            active_skill_bodies_lines.append("")

        return (
            "\n".join(skill_index_lines) if skill_index_lines else "",
            "\n".join(active_skill_bodies_lines) if active_skill_bodies_lines else "",
        )
