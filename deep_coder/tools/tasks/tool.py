from deep_coder.tasks.manager import TaskManager
from deep_coder.tools.base import ToolBase
from deep_coder.tools.result import ToolExecutionResult


def _task_snapshot(tasks: list[dict]) -> dict:
    completed_count = sum(1 for task in tasks if task["status"] == "completed")
    return {
        "type": "task_snapshot",
        "tasks": tasks,
        "completed_count": completed_count,
        "total_count": len(tasks),
    }


def _render_task(task: dict) -> str:
    parts = [f"#{task['id']} {task['status']}: {task['subject']}"]
    if task["blocked_by"]:
        parts.append(f"blocked_by={task['blocked_by']}")
    if task["blocks"]:
        parts.append(f"blocks={task['blocks']}")
    return " | ".join(parts)


def _render_summary(tasks: list[dict]) -> str:
    completed_count = sum(1 for task in tasks if task["status"] == "completed")
    return f"({completed_count}/{len(tasks)} completed)"


def _require_session(session):
    if session is None:
        raise ValueError("task tools require an active session")
    return session


class TaskCreateTool(ToolBase):
    def __init__(self, config, workdir):
        self.config = config
        self.workdir = workdir

    def exec(self, arguments: dict, session=None) -> ToolExecutionResult:
        manager = TaskManager(_require_session(session))
        task = manager.create(
            subject=arguments["subject"],
            description=arguments.get("description", ""),
        )
        return ToolExecutionResult(
            name="task_create",
            display_command="task_create",
            model_output=_render_task(task),
            output_text=_render_task(task),
            timeline_events=[_task_snapshot(manager.list_all())],
        )

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "task_create",
                "description": "Create a session task with optional description.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "subject": {"type": "string"},
                        "description": {"type": "string"},
                    },
                    "required": ["subject"],
                },
            },
        }


class TaskUpdateTool(ToolBase):
    def __init__(self, config, workdir):
        self.config = config
        self.workdir = workdir

    def exec(self, arguments: dict, session=None) -> ToolExecutionResult:
        manager = TaskManager(_require_session(session))
        task = manager.update(
            task_id=arguments["task_id"],
            subject=arguments.get("subject"),
            description=arguments.get("description"),
            status=arguments.get("status"),
            add_blocked_by=arguments.get("add_blocked_by"),
            add_blocks=arguments.get("add_blocks"),
        )
        return ToolExecutionResult(
            name="task_update",
            display_command="task_update",
            model_output=_render_task(task),
            output_text=_render_task(task),
            timeline_events=[_task_snapshot(manager.list_all())],
        )

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "task_update",
                "description": "Update a session task or its dependency graph.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "integer"},
                        "subject": {"type": "string"},
                        "description": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed"],
                        },
                        "add_blocked_by": {
                            "type": "array",
                            "items": {"type": "integer"},
                        },
                        "add_blocks": {
                            "type": "array",
                            "items": {"type": "integer"},
                        },
                    },
                    "required": ["task_id"],
                },
            },
        }


class TaskListTool(ToolBase):
    def __init__(self, config, workdir):
        self.config = config
        self.workdir = workdir

    def exec(self, arguments: dict, session=None) -> ToolExecutionResult:
        manager = TaskManager(_require_session(session))
        tasks = manager.list_all()
        return ToolExecutionResult(
            name="task_list",
            display_command="task_list",
            model_output=_render_summary(tasks),
            output_text=_render_summary(tasks),
            timeline_events=[_task_snapshot(tasks)],
        )

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "task_list",
                "description": "List all session tasks.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        }


class TaskGetTool(ToolBase):
    def __init__(self, config, workdir):
        self.config = config
        self.workdir = workdir

    def exec(self, arguments: dict, session=None) -> ToolExecutionResult:
        manager = TaskManager(_require_session(session))
        task = manager.get(arguments["task_id"])
        return ToolExecutionResult(
            name="task_get",
            display_command="task_get",
            model_output=_render_task(task),
            output_text=_render_task(task),
            timeline_events=[_task_snapshot(manager.list_all())],
        )

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "task_get",
                "description": "Get one session task by id.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "integer"},
                    },
                    "required": ["task_id"],
                },
            },
        }
