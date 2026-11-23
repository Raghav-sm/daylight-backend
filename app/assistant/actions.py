from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Project
from app.schemas.task import TaskCreate, TaskUpdate
from app.services import project_service, task_service


def _matching_projects(db: Session, owner_id: str, name: str) -> list[Project]:
    wanted = name.strip().casefold()
    return [
        project
        for project in project_service.get_projects(db, owner_id)
        if project.name.casefold() == wanted
    ]


def _resolve_project(db: Session, owner_id: str, name: str) -> tuple[Project | None, dict | None]:
    matches = _matching_projects(db, owner_id, name)
    if len(matches) == 1:
        return matches[0], None
    if not matches:
        return None, {"ok": False, "message": f"No project named '{name}' was found."}
    return None, {
        "ok": False,
        "message": "More than one project has that name. Ask the user which one they mean.",
        "matches": [{"id": item.id, "name": item.name} for item in matches],
    }


def list_projects_action(db: Session, owner_id: str) -> list[dict]:
    summaries = project_service.get_project_summaries(db, owner_id)
    projects = {project.id: project for project in project_service.get_projects(db, owner_id)}
    return [
        {
            "id": summary.id,
            "name": summary.name,
            "taskCount": summary.task_count,
            "incompleteTaskCount": summary.incomplete_task_count,
            "stages": [stage.name for stage in projects[summary.id].stages],
        }
        for summary in summaries
    ]


def list_project_tasks_action(db: Session, owner_id: str, project_name: str) -> dict:
    project, error = _resolve_project(db, owner_id, project_name)
    if error:
        return error

    tasks = task_service.get_project_tasks(db, project.id, owner_id)
    return {
        "ok": True,
        "project": project.name,
        "tasks": [
            {
                "id": task.id,
                "title": task.title,
                "stage": task.stage.name if task.stage else None,
                "priority": task.priority,
                "completed": task.completed,
                "dueDate": task.due_date.isoformat() if task.due_date else None,
            }
            for task in tasks[:60]
        ],
        "truncated": len(tasks) > 60,
    }


def create_task_action(
    db: Session,
    owner_id: str,
    project_name: str,
    title: str,
    notes: str = "",
    priority: str = "none",
) -> dict:
    project, error = _resolve_project(db, owner_id, project_name)
    if error:
        return error

    try:
        task = task_service.create_task(
            db,
            project.id,
            owner_id,
            TaskCreate(title=title, notes=notes, priority=priority),
        )
    except HTTPException as error:
        return {"ok": False, "message": error.detail}

    return {
        "ok": True,
        "id": task.id,
        "title": task.title,
        "project": project.name,
        "stage": task.stage.name if task.stage else None,
        "priority": task.priority,
        "completed": task.completed,
    }


def move_task_action(
    db: Session,
    owner_id: str,
    project_name: str,
    task_title: str,
    stage_name: str,
    current_stage: str | None = None,
) -> dict:
    project, error = _resolve_project(db, owner_id, project_name)
    if error:
        return error

    task_matches = [
        task
        for task in task_service.get_project_tasks(db, project.id, owner_id)
        if task.title.casefold() == task_title.strip().casefold()
    ]
    if current_stage:
        task_matches = [
            task
            for task in task_matches
            if task.stage and task.stage.name.casefold() == current_stage.strip().casefold()
        ]
    if not task_matches:
        qualifier = f" in the '{current_stage}' stage" if current_stage else ""
        return {"ok": False, "message": f"No task titled '{task_title}'{qualifier} was found in {project.name}."}
    if len(task_matches) > 1:
        return {
            "ok": False,
            "message": "Several tasks have that title. Ask the user to identify the task by its current stage or other detail.",
            "matches": [
                {"id": task.id, "title": task.title, "stage": task.stage.name if task.stage else None}
                for task in task_matches
            ],
        }

    stages = [stage for stage in project.stages if stage.name.casefold() == stage_name.strip().casefold()]
    if not stages:
        return {
            "ok": False,
            "message": f"No stage named '{stage_name}' exists in {project.name}.",
            "availableStages": [stage.name for stage in project.stages],
        }

    try:
        task = task_service.update_task(
            db,
            task_matches[0].id,
            owner_id,
            TaskUpdate(stage_id=stages[0].id),
        )
    except HTTPException as error:
        return {"ok": False, "message": error.detail}
    return {
        "ok": True,
        "id": task.id,
        "title": task.title,
        "project": project.name,
        "stage": task.stage.name if task.stage else None,
        "completed": task.completed,
    }
