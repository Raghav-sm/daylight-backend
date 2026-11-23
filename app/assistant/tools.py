from typing import Literal

from langchain.tools import tool

from app.assistant.actions import (
    create_task_action,
    list_project_tasks_action,
    list_projects_action,
    move_task_action,
)
from app.database import SessionLocal


def build_tools(owner_id: str):
    """Build per-user tools; authenticated identity is closed over, never model-supplied."""

    @tool
    def list_projects() -> list[dict]:
        """List the signed-in user's projects, stages, and task counts."""
        with SessionLocal() as db:
            return list_projects_action(db, owner_id)

    @tool
    def list_project_tasks(project_name: str) -> dict:
        """List tasks in one of the signed-in user's projects by its exact project name."""
        with SessionLocal() as db:
            return list_project_tasks_action(db, owner_id, project_name)

    @tool
    def create_task(
        project_name: str,
        title: str,
        notes: str = "",
        priority: Literal["none", "low", "medium", "high"] = "none",
    ) -> dict:
        """Create a task in one of the user's projects. Use the exact project name from list_projects."""
        with SessionLocal() as db:
            return create_task_action(db, owner_id, project_name, title, notes, priority)

    @tool
    def move_task(
        project_name: str,
        task_title: str,
        stage_name: str,
        current_stage: str | None = None,
    ) -> dict:
        """Move one task to a stage using exact project, task, and stage names; use current_stage to distinguish duplicates."""
        with SessionLocal() as db:
            return move_task_action(db, owner_id, project_name, task_title, stage_name, current_stage)

    return [list_projects, list_project_tasks, create_task, move_task]
