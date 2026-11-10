from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Project, Stage, Subtask, Task
from app.schemas.task import TaskCreate, TaskUpdate


def _find_stage(project: Project, *, completed: bool) -> Stage | None:
    target_name = "completed" if completed else "to do"
    return next(
        (stage for stage in project.stages if stage.name.casefold() == target_name),
        project.stages[0] if project.stages else None,
    )


def create_task(db: Session, project_id: str, task_data: TaskCreate):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    stage = None
    if task_data.stage_id is not None:
        stage = db.get(Stage, task_data.stage_id)
        if stage is None or stage.project_id != project_id:
            raise HTTPException(status_code=422, detail="Stage does not belong to this project")
    else:
        stage = _find_stage(project, completed=False)

    task = Task(
        project_id=project_id,
        title=task_data.title.strip(),
        notes=task_data.notes,
        due_date=task_data.due_date,
        due_time=task_data.due_time,
        priority=task_data.priority,
        stage_id=stage.id if stage else None,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return get_task(db, task.id)


def get_tasks(db: Session):
    statement = select(Task).options(selectinload(Task.subtasks)).order_by(Task.created_at.desc())
    return db.scalars(statement).all()


def get_project_tasks(db: Session, project_id: str):
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    statement = (
        select(Task)
        .options(selectinload(Task.subtasks))
        .where(Task.project_id == project_id)
        .order_by(Task.created_at.desc())
    )
    return db.scalars(statement).all()


def get_task(db: Session, task_id: str):
    statement = (
        select(Task)
        .options(selectinload(Task.subtasks))
        .where(Task.id == task_id)
    )
    task = db.scalar(statement)
    if task is not None:
        return task

    raise HTTPException(status_code=404, detail="Task not found")


def _replace_subtasks(db: Session, task: Task, submitted_subtasks: list[dict]):
    existing_by_id = {subtask.id: subtask for subtask in task.subtasks}
    updated_subtasks: list[Subtask] = []

    for position, submitted in enumerate(submitted_subtasks):
        subtask_id = submitted.get("id")
        subtask = existing_by_id.get(subtask_id) if subtask_id else None
        if subtask is None:
            subtask = Subtask(
                id=subtask_id,
                title=submitted["title"].strip(),
                completed=submitted.get("completed", False),
                position=position,
            )
        else:
            subtask.title = submitted["title"].strip()
            subtask.completed = submitted.get("completed", False)
            subtask.position = position
        updated_subtasks.append(subtask)

    task.subtasks = updated_subtasks


def update_task(db: Session, task_id: str, task_updates: TaskUpdate):
    task = get_task(db, task_id)
    changes = task_updates.model_dump(exclude_unset=True)
    subtasks_data = changes.pop("subtasks", None)
    new_project_id = changes.pop("project_id", task.project_id)
    project_changed = new_project_id != task.project_id
    stage_was_sent = "stage_id" in changes
    requested_stage_id = changes.pop("stage_id", None)

    project = db.get(Project, new_project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    for field in ("title", "notes", "priority", "due_date", "due_time"):
        if field in changes:
            value = changes[field]
            if value is None and field in {"title", "notes", "priority"}:
                raise HTTPException(status_code=422, detail=f"{field} cannot be null")
            setattr(task, field, value.strip() if field == "title" and value else value)

    if "completed" in changes and changes["completed"] is None:
        raise HTTPException(status_code=422, detail="completed cannot be null")

    task.project_id = new_project_id

    if stage_was_sent and requested_stage_id is not None:
        stage = db.get(Stage, requested_stage_id)
        if stage is None or stage.project_id != new_project_id:
            raise HTTPException(status_code=422, detail="Stage does not belong to this project")
        task.stage_id = stage.id
        task.completed = stage.name.casefold() == "completed"
    elif stage_was_sent:
        task.stage_id = None
        if "completed" in changes:
            task.completed = changes["completed"]
    elif "completed" in changes:
        task.completed = changes["completed"]
        stage = _find_stage(project, completed=task.completed)
        task.stage_id = stage.id if stage else None
    elif project_changed:
        stage = _find_stage(project, completed=task.completed)
        task.stage_id = stage.id if stage else None

    # Compare against the current completion timestamp after applying the update.
    if task.completed:
        if task.completed_at is None:
            task.completed_at = datetime.now(timezone.utc)
    else:
        task.completed_at = None

    if subtasks_data is not None:
        _replace_subtasks(db, task, subtasks_data)

    db.commit()
    return get_task(db, task.id)


def delete_task(db: Session, task_id: str):
    task = get_task(db, task_id)
    db.delete(task)
    db.commit()
