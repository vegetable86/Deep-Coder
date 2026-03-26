class TaskManager:
    def __init__(self, session):
        self.session = session

    def create(self, subject: str, description: str = "") -> dict:
        task = {
            "id": self.session.next_task_id,
            "subject": subject,
            "description": description,
            "status": "pending",
            "blocked_by": [],
            "blocks": [],
        }
        self.session.tasks.append(task)
        self.session.next_task_id += 1
        return task

    def get(self, task_id: int) -> dict:
        for task in self.session.tasks:
            if task["id"] == task_id:
                return task
        raise ValueError(f"unknown task id: {task_id}")

    def update(
        self,
        task_id: int,
        subject: str | None = None,
        description: str | None = None,
        status: str | None = None,
        add_blocked_by: list[int] | None = None,
        add_blocks: list[int] | None = None,
    ) -> dict:
        task = self.get(task_id)
        if subject is not None:
            task["subject"] = subject
        if description is not None:
            task["description"] = description
        for blocker_id in add_blocked_by or []:
            self._link_dependency(blocker_id, task_id)
        for blocked_id in add_blocks or []:
            self._link_dependency(task_id, blocked_id)
        if status is not None:
            task["status"] = status
            if status == "completed":
                for blocked_id in list(task["blocks"]):
                    blocked = self.get(blocked_id)
                    if task_id in blocked["blocked_by"]:
                        blocked["blocked_by"].remove(task_id)
        return task

    def list_all(self) -> list[dict]:
        return list(self.session.tasks)

    def _link_dependency(self, blocker_id: int, blocked_id: int) -> None:
        if blocker_id == blocked_id:
            raise ValueError("task cannot depend on itself")
        blocker = self.get(blocker_id)
        blocked = self.get(blocked_id)
        if blocked_id not in blocker["blocks"]:
            blocker["blocks"].append(blocked_id)
        if blocker_id not in blocked["blocked_by"]:
            blocked["blocked_by"].append(blocker_id)
