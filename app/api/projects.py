from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate, StageCreate, StageRead
from app.services import project_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", status_code=201, response_model=ProjectRead)
def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
    return project_service.create_project(db, project)


@router.get("", status_code=200, response_model=list[ProjectRead])
def get_projects(db: Session = Depends(get_db)):
    return project_service.get_projects(db)


@router.get("/{project_id}", status_code=200, response_model=ProjectRead)
def get_project(project_id: str, db: Session = Depends(get_db)):
    return project_service.get_project(db, project_id)


@router.patch("/{project_id}", status_code=200, response_model=ProjectRead)
def update_project(
    project_id: str,
    project: ProjectUpdate,
    db: Session = Depends(get_db),
):
    return project_service.update_project(db, project_id, project)


@router.post("/{project_id}/stages", status_code=201, response_model=StageRead)
def add_project_stage(
    project_id: str,
    stage: StageCreate,
    db: Session = Depends(get_db),
):
    return project_service.add_project_stage(db, project_id, stage)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, db: Session = Depends(get_db)):
    project_service.delete_project(db, project_id)
