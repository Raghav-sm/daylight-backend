from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Project, Stage
from app.schemas.project import ProjectCreate, ProjectUpdate, StageCreate

DEFAULT_STAGES = (
    ("To Do", "blue"),
    ("In Progress", "amber"),
    ("Completed", "green"),
)


def create_project(db: Session, project_data: ProjectCreate):
    project = Project(
        name=project_data.name.strip(),
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
        setattr(project, field, value.strip() if field == "name" else value)

    db.commit()
    return get_project(db, project_id)


def add_project_stage(db: Session, project_id: str, stage_data: StageCreate):
    project = get_project(db, project_id)
    stage_name = stage_data.name.strip()
    if any(stage.name.casefold() == stage_name.casefold() for stage in project.stages):
        raise HTTPException(status_code=409, detail="A stage with that name already exists")

    stage = Stage(
        project_id=project.id,
        name=stage_name,
        color=stage_data.color,
        position=len(project.stages),
    )
    db.add(stage)
    db.commit()
    db.refresh(stage)
    return stage


def delete_project(db: Session, project_id: str):
    project = get_project(db, project_id)
    if project.tasks:
        raise HTTPException(
            status_code=409,
            detail="Delete the project's tasks before deleting the project",
        )

    db.delete(project)
    db.commit()
