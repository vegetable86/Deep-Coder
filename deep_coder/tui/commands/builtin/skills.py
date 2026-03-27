from deep_coder.tui.commands.base import CommandBase, CommandMatch, CommandResult
from deep_coder.skills.registry import SkillRegistry


class SkillsCommand(CommandBase):
    name = "skills"
    summary = "List and manage active skills"
    argument_hint = "[list|activate <name>|deactivate <name>]"

    def complete(self, context, args: str):
        parts = args.strip().split()
        if len(parts) == 0:
            return [
                CommandMatch(
                    name="list",
                    summary="List available skills",
                    label="list",
                    command_text="/skills list",
                    kind="subcommand",
                ),
                CommandMatch(
                    name="activate",
                    summary="Activate a skill",
                    label="activate",
                    command_text="/skills activate ",
                    kind="subcommand",
                ),
                CommandMatch(
                    name="deactivate",
                    summary="Deactivate a skill",
                    label="deactivate",
                    command_text="/skills deactivate ",
                    kind="subcommand",
                ),
            ]
        elif len(parts) == 1:
            subcommand = parts[0]
            if subcommand in ["activate", "deactivate"]:
                config = context.runtime["config"]
                registry = SkillRegistry(root=config.skills_dir)
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
        return []

    def execute(self, context, args: str) -> CommandResult:
        parts = args.strip().split()
        subcommand = parts[0] if parts else "list"

        config = context.runtime["config"]
        registry = SkillRegistry(root=config.skills_dir)

        if subcommand == "list":
            try:
                skills = registry.list_skills()
            except Exception as e:
                return CommandResult(
                    status_message=f"Failed to list skills: {e}",
                )

            active_names = {s["name"] for s in context.session.active_skills}

            lines = []
            for skill in skills:
                status = "✓" if skill.name in active_names else " "
                lines.append(f"[bold]{status} {skill.name}[/bold] - {skill.title}")
                lines.append(f"    {skill.summary}")
                if skill.tags:
                    lines.append(f"    tags: {', '.join(skill.tags)}")
                lines.append("")

            if not lines:
                lines.append("No skills found in global registry.")

            return CommandResult(
                status_message="\n".join(lines),
            )

        elif subcommand == "activate":
            if len(parts) < 2:
                return CommandResult(
                    status_message="Usage: /skills activate <skill-name>",
                )
            name = parts[1]

            try:
                skill = registry.load_skill(name)
            except FileNotFoundError:
                return CommandResult(
                    status_message=f"Skill '{name}' not found",
                )

            # Check if already active
            active_names = {s["name"] for s in context.session.active_skills}
            if name in active_names:
                return CommandResult(
                    status_message=f"Skill '{name}' is already active",
                )

            # Add to active skills
            import hashlib
            from datetime import datetime

            body_hash = hashlib.sha256(skill.body.encode("utf-8")).hexdigest()
            skill_hash = f"sha256:{body_hash}"

            skill_record = {
                "name": skill.name,
                "title": skill.title,
                "hash": skill_hash,
                "activated_at": datetime.utcnow().isoformat() + "Z",
                "source": "user",
            }

            context.session.active_skills.append(skill_record)

            return CommandResult(
                status_message=f"Skill '{name}' activated",
            )

        elif subcommand == "deactivate":
            if len(parts) < 2:
                return CommandResult(
                    status_message="Usage: /skills deactivate <skill-name>",
                )
            name = parts[1]

            # Remove from active skills
            original_len = len(context.session.active_skills)
            context.session.active_skills = [
                s for s in context.session.active_skills if s["name"] != name
            ]

            if len(context.session.active_skills) < original_len:
                return CommandResult(
                    status_message=f"Skill '{name}' deactivated",
                )
            else:
                return CommandResult(
                    status_message=f"Skill '{name}' was not active",
                )

        else:
            return CommandResult(
                status_message=f"Unknown subcommand: {subcommand}",
            )