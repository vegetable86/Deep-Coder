from deep_coder.tui.commands.base import CommandBase, CommandMatch, CommandResult
from deep_coder.skills.registry import SkillRegistry


class SkillsCommand(CommandBase):
    name = "skills"
    summary = "List and manage active skills"
    argument_hint = "[use <name>|drop <name>|clear|show <name>]"

    def complete(self, context, args: str):
        parts = args.strip().split()
        if len(parts) == 0:
            return _subcommand_matches(prefix="")
        if len(parts) == 1:
            subcommand = parts[0]
            if subcommand in {"use", "drop", "show"}:
                return self._skill_matches(context, subcommand)
            return _subcommand_matches(prefix=subcommand)
        return []

    def execute(self, context, args: str) -> CommandResult:
        parts = args.strip().split()
        subcommand = parts[0] if parts else "list"

        config = context.runtime["config"]
        registry = SkillRegistry(root=config.skills_dir)
        session = _current_session(context, create=subcommand in {"use", "clear"})
        active_names = {skill["name"] for skill in getattr(session, "active_skills", [])} if session else set()

        if subcommand in {"list", ""}:
            try:
                skills = registry.list_skills()
            except Exception as e:
                return CommandResult(
                    status_message=f"Failed to list skills: {e}",
                )

            if not skills:
                return CommandResult(status_message="skills: none")

            items = []
            for skill in skills:
                marker = "*" if skill.name in active_names else "-"
                items.append(f"{marker}{skill.name}")
            return CommandResult(
                status_message="skills: " + ", ".join(items),
            )

        if subcommand in {"use", "activate"}:
            if len(parts) < 2:
                return CommandResult(
                    status_message="usage: /skills use <skill-name>",
                )
            name = parts[1]

            try:
                skill = registry.load_skill(name)
            except FileNotFoundError:
                return CommandResult(
                    warning_message=f"skill not found: {name}",
                )

            if session is None:
                return CommandResult(warning_message="unable to open session")

            context_manager = context.runtime["context"]
            record, activated = context_manager.activate_skill(session, skill, source="user")
            if not activated:
                return CommandResult(
                    status_message=f"skill already active: {name}",
                    selected_session_id=session.session_id,
                )
            event = {
                "type": "skill_activated",
                "session_id": session.session_id,
                "turn_id": "command",
                "name": record["name"],
                "title": record["title"],
                "source": record["source"],
                "hash": record["hash"],
            }
            session.events.append(event)
            context_manager.flush(session)
            return CommandResult(
                status_message=f"skill active: {name}",
                selected_session_id=session.session_id,
                timeline_events=[event],
            )

        if subcommand in {"drop", "deactivate"}:
            if len(parts) < 2:
                return CommandResult(
                    status_message="usage: /skills drop <skill-name>",
                )
            name = parts[1]
            if session is None:
                return CommandResult(
                    status_message=f"skill not active: {name}",
                )
            removed = context.runtime["context"].deactivate_skill(session, name)
            if not removed:
                return CommandResult(
                    status_message=f"skill not active: {name}",
                    selected_session_id=session.session_id,
                )
            event = {
                "type": "skill_dropped",
                "session_id": session.session_id,
                "turn_id": "command",
                "name": name,
            }
            session.events.append(event)
            context.runtime["context"].flush(session)
            return CommandResult(
                status_message=f"skill removed: {name}",
                selected_session_id=session.session_id,
                timeline_events=[event],
            )

        if subcommand == "clear":
            if session is None or not session.active_skills:
                return CommandResult(status_message="no active skills")
            cleared = context.runtime["context"].clear_skills(session)
            events = [
                {
                    "type": "skill_dropped",
                    "session_id": session.session_id,
                    "turn_id": "command",
                    "name": skill["name"],
                }
                for skill in cleared
            ]
            session.events.extend(events)
            context.runtime["context"].flush(session)
            return CommandResult(
                status_message="cleared active skills",
                selected_session_id=session.session_id,
                timeline_events=events,
            )

        if subcommand == "show":
            if len(parts) < 2:
                return CommandResult(status_message="usage: /skills show <skill-name>")
            name = parts[1]
            try:
                skill = registry.load_skill(name)
            except FileNotFoundError:
                return CommandResult(warning_message=f"skill not found: {name}")
            tags = f" | tags: {', '.join(skill.tags)}" if skill.tags else ""
            return CommandResult(
                status_message=f"{skill.name}: {skill.title} - {skill.summary}{tags}",
            )

        return CommandResult(warning_message=f"unknown /skills subcommand: {subcommand}")

    @staticmethod
    def _skill_matches(context, subcommand: str) -> list[CommandMatch]:
        registry = SkillRegistry(root=context.runtime["config"].skills_dir)
        try:
            skills = registry.list_skills()
        except Exception:
            skills = []
        return [
            CommandMatch(
                name=skill.name,
                summary=skill.summary,
                label=skill.name,
                command_text=f"/skills {subcommand} {skill.name}",
                kind="skill",
            )
            for skill in skills
        ]


def _current_session(context, *, create: bool):
    runtime_context = context.runtime["context"]
    if context.session_id:
        return runtime_context.open(locator={"id": context.session_id})
    if create:
        return runtime_context.open()
    return None


def _subcommand_matches(prefix: str) -> list[CommandMatch]:
    subcommands = [
        ("list", "List available skills"),
        ("use", "Activate a skill for this session"),
        ("drop", "Remove one active skill"),
        ("clear", "Remove all active skills"),
        ("show", "Show one skill summary"),
    ]
    return [
        CommandMatch(
            name=name,
            summary=summary,
            label=name,
            command_text=f"/skills {name}" + (" " if name in {"use", "drop", "show"} else ""),
            kind="subcommand",
        )
        for name, summary in subcommands
        if name.startswith(prefix)
    ]
