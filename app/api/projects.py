from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuthSession, User
from app.security.dependencies import get_current_user, require_csrf
from app.schemas.project import (
    ProjectCreate,
    ProjectRead,
    ProjectSummary,
    ProjectUpdate,
    StageCreate,
    StageOrderUpdate,
    StageRead,
)
from app.schemas.task import TaskCreate, TaskRead, TaskSummary
from app.services import project_service, task_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", status_code=201, response_model=ProjectRead)
def create_project(
    project: ProjectCreate,
    user: User = Depends(get_current_user),
    _csrf: AuthSession = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    return project_service.create_project(db, project, user.id)


@router.get("", status_code=200, response_model=list[ProjectRead])
def get_projects(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return project_service.get_projects(db, user.id)


@router.get("/summary", status_code=200, response_model=list[ProjectSummary])
def get_project_summaries(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return project_service.get_project_summaries(db, user.id)


@router.get("/{project_id}", status_code=200, response_model=ProjectRead)
def get_project(
    project_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return project_service.get_project(db, project_id, user.id)


@router.patch("/{project_id}", status_code=200, response_model=ProjectRead)
def update_project(
    project_id: str,
    project: ProjectUpdate,
    user: User = Depends(get_current_user),
    _csrf: AuthSession = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    return project_service.update_project(db, project_id, project, user.id)


@router.post("/{project_id}/stages", status_code=201, response_model=StageRead)
def add_project_stage(
    project_id: str,
    stage: StageCreate,
    user: User = Depends(get_current_user),
    _csrf: AuthSession = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    return project_service.add_project_stage(db, project_id, stage, user.id)


@router.put("/{project_id}/stages/order", status_code=200, response_model=ProjectRead)
def reorder_project_stages(
    project_id: str,
    order: StageOrderUpdate,
    user: User = Depends(get_current_user),
    _csrf: AuthSession = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    return project_service.reorder_project_stages(db, project_id, order.stage_ids, user.id)


@router.delete("/{project_id}/stages/{stage_id}", status_code=204)
def delete_project_stage(
    project_id: str,
    stage_id: str,
    target_stage_id: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    _csrf: AuthSession = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    project_service.delete_project_stage(db, project_id, stage_id, target_stage_id, user.id)


@router.post("/{project_id}/tasks", status_code=201, response_model=TaskRead)
def create_task(
    project_id: str,
    task: TaskCreate,
    user: User = Depends(get_current_user),
    _csrf: AuthSession = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    return task_service.create_task(db, project_id, user.id, task)


@router.get("/{project_id}/tasks", status_code=200, response_model=list[TaskRead])
def get_project_tasks(
    project_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return task_service.get_project_tasks(db, project_id, user.id)


@router.get(
    "/{project_id}/tasks/summary",
    status_code=200,
    response_model=list[TaskSummary],
)
def get_project_task_summaries(
    project_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return task_service.get_project_task_summaries(db, project_id, user.id)


@router.delete("/{project_id}", status_code=204)
def delete_project(
    project_id: str,
    user: User = Depends(get_current_user),
    _csrf: AuthSession = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    project_service.delete_project(db, project_id, user.id)
