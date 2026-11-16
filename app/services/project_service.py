from fastapi import HTTPException
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Project, Stage, Task
from app.schemas.project import ProjectCreate, ProjectSummary, ProjectUpdate, StageCreate

DEFAULT_STAGES = (
    ("To Do", "blue"),
    ("In Progress", "amber"),
    ("Completed", "green"),
)


def create_project(db: Session, project_data: ProjectCreate):
    project = Project(
        name=project_data.name,
        color=project_data.color,
        stages=[
            Stage(name=name, color=color, position=position)
            for position, (name, color) in enumerate(DEFAULT_STAGES)
        ],
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return get_project(db, project.id)


def get_projects(db: Session):
    statement = select(Project).options(selectinload(Project.stages)).order_by(Project.name)
    return db.scalars(statement).all()


def get_project_summaries(db: Session) -> list[ProjectSummary]:
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


def get_project(db: Session, project_id: str):
    statement = (
        select(Project)
        .options(selectinload(Project.stages))
        .where(Project.id == project_id)
    )
    project = db.scalar(statement)
    if project is not None:
        return project

    raise HTTPException(status_code=404, detail="Project not found")


def update_project(db: Session, project_id: str, project_data: ProjectUpdate):
    project = get_project(db, project_id)
    changes = project_data.model_dump(exclude_unset=True)

    for field, value in changes.items():
        if value is None:
            raise HTTPException(status_code=422, detail=f"{field} cannot be null")
        setattr(project, field, value)

    db.commit()
    return get_project(db, project_id)


def add_project_stage(db: Session, project_id: str, stage_data: StageCreate):
    project = get_project(db, project_id)
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


def delete_project(db: Session, project_id: str):
    project = get_project(db, project_id)
    has_tasks = db.scalar(select(exists().where(Task.project_id == project_id)))
    if has_tasks:
        raise HTTPException(
            status_code=409,
            detail="Delete the project's tasks before deleting the project",
        )

    db.delete(project)
    db.commit()
