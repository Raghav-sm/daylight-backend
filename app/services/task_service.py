from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Project, Stage, Subtask, Task
from app.schemas.task import TaskCreate, TaskSummary, TaskUpdate


def _find_stage(project: Project, *, completed: bool) -> Stage | None:
    target_id = project.final_stage_id if completed else project.initial_stage_id
    return next(
        (stage for stage in project.stages if stage.id == target_id),
        project.stages[0] if project.stages else None,
    )


def _apply_completion_timestamp(task: Task) -> None:
    if task.completed:
        if task.completed_at is None:
            task.completed_at = datetime.now(timezone.utc)
    else:
        task.completed_at = None


def create_task(db: Session, project_id: str, owner_id: str, task_data: TaskCreate):
    project = (
        db.scalars(
            select(Project)
            .options(selectinload(Project.stages))
            .where(Project.id == project_id, Project.owner_id == owner_id)
        ).first()
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    stage = None
    if task_data.stage_id is not None:
        stage = db.get(Stage, task_data.stage_id)
        if stage is None or stage.project_id != project_id:
            raise HTTPException(status_code=422, detail="Stage does not belong to this project")
    else:
        stage = _find_stage(project, completed=False)

    completed = bool(stage and stage.id == project.final_stage_id)

    task = Task(
        project_id=project_id,
        title=task_data.title,
        notes=task_data.notes,
        due_date=task_data.due_date,
        due_time=task_data.due_time if task_data.due_date is not None else None,
        priority=task_data.priority,
        stage_id=stage.id if stage else None,
        completed=completed,
        completed_at=datetime.now(timezone.utc) if completed else None,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return get_task(db, task.id, owner_id)


def get_tasks(db: Session, owner_id: str):
    statement = (
        select(Task)
        .join(Project, Task.project_id == Project.id)
        .options(selectinload(Task.subtasks))
        .where(Project.owner_id == owner_id)
        .order_by(Task.created_at.desc())
    )
    return db.scalars(statement).all()


def get_project_tasks(db: Session, project_id: str, owner_id: str):
    if db.scalar(select(Project.id).where(Project.id == project_id, Project.owner_id == owner_id)) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    statement = (
        select(Task)
        .options(selectinload(Task.subtasks))
        .where(Task.project_id == project_id)
        .order_by(Task.created_at.desc())
    )
    return db.scalars(statement).all()


def get_project_task_summaries(db: Session, project_id: str, owner_id: str) -> list[TaskSummary]:
    if db.scalar(select(Project.id).where(Project.id == project_id, Project.owner_id == owner_id)) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    subtask_counts = (
        select(
            Subtask.task_id.label("task_id"),
            func.count(Subtask.id).label("subtask_count"),
            func.count(Subtask.id).filter(Subtask.completed.is_(True)).label("completed_subtask_count"),
        )
        .group_by(Subtask.task_id)
        .subquery()
    )

    statement = (
        select(
            Task.id,
            Task.project_id,
            Task.title,
            Task.due_date,
            Task.due_time,
            Task.priority,
            Task.completed,
            Task.stage_id,
            func.coalesce(subtask_counts.c.subtask_count, 0),
            func.coalesce(subtask_counts.c.completed_subtask_count, 0),
        )
        .outerjoin(subtask_counts, subtask_counts.c.task_id == Task.id)
        .join(Project, Task.project_id == Project.id)
        .where(Task.project_id == project_id, Project.owner_id == owner_id)
        .order_by(Task.created_at.desc())
    )

    return [
        TaskSummary(
            id=row[0],
            project_id=row[1],
            title=row[2],
            due_date=row[3],
            due_time=row[4],
            priority=row[5],
            completed=row[6],
            stage_id=row[7],
            subtask_count=row[8],
            completed_subtask_count=row[9],
        )
        for row in db.execute(statement).all()
    ]


def get_task(db: Session, task_id: str, owner_id: str):
    statement = (
        select(Task)
        .options(selectinload(Task.subtasks))
        .join(Project, Task.project_id == Project.id)
        .where(Task.id == task_id, Project.owner_id == owner_id)
    )
    task = db.scalar(statement)
    if task is not None:
        return task

    raise HTTPException(status_code=404, detail="Task not found")


def _replace_subtasks(db: Session, task: Task, submitted_subtasks: list[dict]):
    existing_by_id = {subtask.id: subtask for subtask in task.subtasks}
    seen_ids: set[str] = set()
    updated_subtasks: list[Subtask] = []

    for position, submitted in enumerate(submitted_subtasks):
        subtask_id = submitted.get("id")
        title = submitted["title"]
        completed = submitted.get("completed", False)

        if subtask_id is not None:
            if subtask_id in seen_ids:
                raise HTTPException(status_code=422, detail="Duplicate subtask id")
            seen_ids.add(subtask_id)

            if subtask_id in existing_by_id:
                subtask = existing_by_id[subtask_id]
                subtask.title = title
                subtask.completed = completed
                subtask.position = position
            else:
                owned_elsewhere = db.scalar(
                    select(Subtask.id).where(
                        Subtask.id == subtask_id,
                        Subtask.task_id != task.id,
                    )
                )
                if owned_elsewhere is not None:
                    raise HTTPException(
                        status_code=422,
                        detail="Subtask belongs to another task",
                    )
                subtask = Subtask(
                    id=subtask_id,
                    title=title,
                    completed=completed,
                    position=position,
                )
        else:
            subtask = Subtask(
                title=title,
                completed=completed,
                position=position,
            )

        updated_subtasks.append(subtask)

    task.subtasks = updated_subtasks


def update_task(db: Session, task_id: str, owner_id: str, task_updates: TaskUpdate):
    task = get_task(db, task_id, owner_id)
    changes = task_updates.model_dump(exclude_unset=True)
    fields_set = task_updates.model_fields_set
    subtasks_data = changes.pop("subtasks", None)
    new_project_id = changes.pop("project_id", task.project_id)
    project_changed = new_project_id != task.project_id
    stage_was_sent = "stage_id" in fields_set
    completed_was_sent = "completed" in fields_set
    requested_stage_id = changes.pop("stage_id", None) if stage_was_sent else None

    project = db.scalars(
        select(Project)
        .options(selectinload(Project.stages))
        .where(Project.id == new_project_id, Project.owner_id == owner_id)
    ).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if stage_was_sent and completed_was_sent and requested_stage_id is not None:
        stage = db.get(Stage, requested_stage_id)
        if stage is not None and stage.project_id == new_project_id:
            stage_implies_completed = stage.id == project.final_stage_id
            if stage_implies_completed != changes["completed"]:
                raise HTTPException(
                    status_code=422,
                    detail="stage_id and completed disagree",
                )

    for field in ("title", "notes", "priority"):
        if field in changes:
            value = changes[field]
            if value is None:
                raise HTTPException(status_code=422, detail=f"{field} cannot be null")
            setattr(task, field, value)

    if "due_date" in fields_set:
        task.due_date = changes.get("due_date")
        if task.due_date is None:
            task.due_time = None
        elif "due_time" in fields_set:
            task.due_time = changes.get("due_time")
    elif "due_time" in fields_set:
        if changes.get("due_time") is not None and task.due_date is None:
            raise HTTPException(status_code=422, detail="due_time requires due_date")
        task.due_time = changes.get("due_time")

    if completed_was_sent and changes.get("completed") is None:
        raise HTTPException(status_code=422, detail="completed cannot be null")

    task.project_id = new_project_id

    if stage_was_sent and requested_stage_id is not None:
        stage = db.get(Stage, requested_stage_id)
        if stage is None or stage.project_id != new_project_id:
            raise HTTPException(status_code=422, detail="Stage does not belong to this project")
        task.stage_id = stage.id
        task.completed = stage.id == project.final_stage_id
    elif stage_was_sent:
        task.stage_id = None
        if completed_was_sent:
            task.completed = changes["completed"]
    elif completed_was_sent:
        task.completed = changes["completed"]
        stage = _find_stage(project, completed=task.completed)
        task.stage_id = stage.id if stage else None
    elif project_changed:
        stage = _find_stage(project, completed=task.completed)
        task.stage_id = stage.id if stage else None

    _apply_completion_timestamp(task)

    if subtasks_data is not None:
        _replace_subtasks(db, task, subtasks_data)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not save task") from None
    return get_task(db, task.id, owner_id)


def delete_task(db: Session, task_id: str, owner_id: str):
    task = get_task(db, task_id, owner_id)
    db.delete(task)
    db.commit()
