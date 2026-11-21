from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import exists, func, select, update
from sqlalchemy.orm import Session, selectinload

from app.models import Project, Stage, Task
from app.schemas.project import ProjectCreate, ProjectSummary, ProjectUpdate, StageCreate

DEFAULT_STAGES = (
    ("To Do", "blue"),
    ("In Progress", "amber"),
    ("Completed", "green"),
)


def create_project(db: Session, project_data: ProjectCreate, owner_id: str):
    project = Project(
        name=project_data.name,
        color=project_data.color,
        owner_id=owner_id,
        stages=[
            Stage(name=name, color=color, position=position)
            for position, (name, color) in enumerate(DEFAULT_STAGES)
        ],
    )
    db.add(project)
    db.flush()
    project.initial_stage_id = project.stages[0].id
    project.final_stage_id = project.stages[-1].id
    db.commit()
    db.refresh(project)
    return get_project(db, project.id, owner_id)


def get_projects(db: Session, owner_id: str):
    statement = (
        select(Project)
        .options(selectinload(Project.stages))
        .where(Project.owner_id == owner_id)
        .order_by(Project.name)
    )
    return db.scalars(statement).all()


def get_project_summaries(db: Session, owner_id: str) -> list[ProjectSummary]:
    task_counts = (
        select(
            Task.project_id.label("project_id"),
            func.count(Task.id).label("task_count"),
            func.count(Task.id).filter(Task.completed.is_(False)).label("incomplete_task_count"),
        )
        .group_by(Task.project_id)
        .subquery()
    )
    stage_counts = (
        select(
            Stage.project_id.label("project_id"),
            func.count(Stage.id).label("stage_count"),
        )
        .group_by(Stage.project_id)
        .subquery()
    )

    statement = (
        select(
            Project.id,
            Project.name,
            Project.color,
            func.coalesce(task_counts.c.task_count, 0),
            func.coalesce(task_counts.c.incomplete_task_count, 0),
            func.coalesce(stage_counts.c.stage_count, 0),
        )
        .outerjoin(task_counts, task_counts.c.project_id == Project.id)
        .outerjoin(stage_counts, stage_counts.c.project_id == Project.id)
        .where(Project.owner_id == owner_id)
        .order_by(Project.name)
    )

    return [
        ProjectSummary(
            id=row[0],
            name=row[1],
            color=row[2],
            task_count=row[3],
            incomplete_task_count=row[4],
            stage_count=row[5],
        )
        for row in db.execute(statement).all()
    ]


def get_project(db: Session, project_id: str, owner_id: str):
    statement = (
        select(Project)
        .options(selectinload(Project.stages))
        .where(Project.id == project_id, Project.owner_id == owner_id)
    )
    project = db.scalar(statement)
    if project is not None:
        return project

    raise HTTPException(status_code=404, detail="Project not found")


def update_project(db: Session, project_id: str, project_data: ProjectUpdate, owner_id: str):
    project = get_project(db, project_id, owner_id)
    changes = project_data.model_dump(exclude_unset=True)

    stage_ids = {stage.id for stage in project.stages}
    for field in ("initial_stage_id", "final_stage_id"):
        if field in changes and changes[field] not in stage_ids:
            raise HTTPException(status_code=422, detail=f"{field} must belong to this project")
    initial_id = changes.get("initial_stage_id", project.initial_stage_id)
    final_id = changes.get("final_stage_id", project.final_stage_id)
    if initial_id == final_id and len(stage_ids) > 1:
        if "initial_stage_id" in changes and "final_stage_id" not in changes:
            final_id = project.initial_stage_id
            changes["final_stage_id"] = final_id
        elif "final_stage_id" in changes and "initial_stage_id" not in changes:
            initial_id = project.final_stage_id
            changes["initial_stage_id"] = initial_id
        else:
            raise HTTPException(status_code=422, detail="Initial and final stages must be different")

    for field, value in changes.items():
        if value is None:
            raise HTTPException(status_code=422, detail=f"{field} cannot be null")
        setattr(project, field, value)

    if "final_stage_id" in changes:
        for task in db.scalars(select(Task).where(Task.project_id == project_id)):
            task.completed = task.stage_id == final_id
            if task.completed:
                if task.completed_at is None:
                    task.completed_at = datetime.now(timezone.utc)
            else:
                task.completed_at = None

    db.commit()
    return get_project(db, project_id, owner_id)


def reorder_project_stages(db: Session, project_id: str, stage_ids: list[str], owner_id: str):
    project = get_project(db, project_id, owner_id)
    if len(stage_ids) != len(project.stages) or set(stage_ids) != {stage.id for stage in project.stages}:
        raise HTTPException(status_code=422, detail="Include every project stage exactly once")
    positions = {stage_id: position for position, stage_id in enumerate(stage_ids)}
    for stage in project.stages:
        stage.position = positions[stage.id]
    db.commit()
    db.expire(project, ["stages"])
    return get_project(db, project_id, owner_id)


def add_project_stage(db: Session, project_id: str, stage_data: StageCreate, owner_id: str):
    project = get_project(db, project_id, owner_id)
    stage_name = stage_data.name
    if any(stage.name.casefold() == stage_name.casefold() for stage in project.stages):
        raise HTTPException(status_code=409, detail="A stage with that name already exists")

    stage = Stage(
        project_id=project.id,
        name=stage_name,
        color=stage_data.color,
        position=len(project.stages),
    )
    db.add(stage)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="A stage with that name already exists") from None
    db.refresh(stage)
    return stage


def delete_project_stage(
    db: Session,
    project_id: str,
    stage_id: str,
    target_stage_id: str | None,
    owner_id: str,
):
    project = get_project(db, project_id, owner_id)
    stage = next((item for item in project.stages if item.id == stage_id), None)
    if stage is None:
        raise HTTPException(status_code=404, detail="Stage not found")
    if len(project.stages) <= 1:
        raise HTTPException(status_code=409, detail="A project must have at least one stage")

    task_count = db.scalar(select(func.count(Task.id)).where(Task.stage_id == stage.id)) or 0
    target_stage = None
    if task_count:
        if target_stage_id is None:
            raise HTTPException(status_code=409, detail="Choose another stage for the tasks in this stage")
        target_stage = next((item for item in project.stages if item.id == target_stage_id), None)
        if target_stage is None or target_stage.id == stage.id:
            raise HTTPException(status_code=422, detail="Choose a different stage in this project")
        db.execute(
            update(Task).where(Task.stage_id == stage.id).values(stage_id=target_stage.id)
        )

    remaining_stages = [item for item in project.stages if item.id != stage.id]
    if project.initial_stage_id == stage.id:
        project.initial_stage_id = remaining_stages[0].id
    if project.final_stage_id == stage.id:
        project.final_stage_id = remaining_stages[-1].id
    for task in db.scalars(select(Task).where(Task.project_id == project_id)):
        task.completed = task.stage_id == project.final_stage_id
        task.completed_at = (task.completed_at or datetime.now(timezone.utc)) if task.completed else None
    db.delete(stage)
    for position, remaining_stage in enumerate(remaining_stages):
        remaining_stage.position = position
    db.commit()


def delete_project(db: Session, project_id: str, owner_id: str):
    project = get_project(db, project_id, owner_id)
    has_tasks = db.scalar(select(exists().where(Task.project_id == project_id)))
    if has_tasks:
        raise HTTPException(
            status_code=409,
            detail="Delete the project's tasks before deleting the project",
        )

    db.delete(project)
    db.commit()
