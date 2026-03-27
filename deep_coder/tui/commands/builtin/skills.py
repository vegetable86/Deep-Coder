from deep_coder.tui.commands.base import CommandBase, CommandMatch, CommandResult
from deep_coder.skills.registry import SkillRegistry


class SkillsCommand(CommandBase):
    name = "skills"
    summary = "List skills and browse skill content"
    argument_hint = "[list|show]"

    def complete(self, context, args: str):
        parts = args.strip().split()
        if len(parts) == 0:
            return _subcommand_matches(prefix="")
        if len(parts) == 1:
            return _subcommand_matches(prefix=parts[0])
        return []

    def execute(self, context, args: str) -> CommandResult:
        parts = args.strip().split()
        subcommand = parts[0] if parts else "list"

        config = context.runtime["config"]
        registry = SkillRegistry(root=config.skills_dir)
        session = _current_session(context, create=False)
        active_names = {skill["name"] for skill in getattr(session, "active_skills", [])} if session else set()

        if subcommand in {"list", ""}:
            try:
                skills = registry.list_skills()
            except Exception as e:
                return CommandResult(
                    status_message=f"Failed to list skills: {e}",
                )

            return CommandResult(
                list_items=_skill_items(skills, active_names=active_names, include_body=False),
                list_kind="skills",
            )

        if subcommand == "show":
            try:
                skills = registry.list_skills()
            except Exception as e:
                return CommandResult(status_message=f"Failed to list skills: {e}")
            return CommandResult(
                list_items=_skill_items(skills, active_names=active_names, include_body=True),
                list_kind="skills_show",
            )

        return CommandResult(warning_message=f"unknown /skills subcommand: {subcommand}")


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
        ("show", "Browse installed skill content"),
    ]
    return [
        CommandMatch(
            name=name,
            summary=summary,
            label=name,
            command_text=f"/skills {name}",
            kind="subcommand",
        )
        for name, summary in subcommands
        if name.startswith(prefix)
    ]


def _skill_items(skills, *, active_names: set[str], include_body: bool) -> list[dict]:
    items = []
    for skill in skills:
        item = {
            "name": skill.name,
            "title": skill.title,
            "summary": skill.summary,
            "is_active": skill.name in active_names,
        }
        if include_body:
            item["body"] = skill.body
        items.append(item)
    return items
