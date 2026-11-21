from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuthSession, User
from app.security.dependencies import get_current_user, require_csrf
from app.schemas.task import TaskRead, TaskUpdate
from app.services import task_service

router = APIRouter(tags=["tasks"])


@router.get("/tasks", status_code=200, response_model=list[TaskRead])
def get_tasks(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """List this user's tasks. Prefer project-scoped summaries for the app."""
    return task_service.get_tasks(db, user.id)


@router.get("/tasks/{task_id}", status_code=200, response_model=TaskRead)
def get_task(task_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return task_service.get_task(db, task_id, user.id)


@router.patch("/tasks/{task_id}", status_code=200, response_model=TaskRead)
def update_task(
    task_id: str,
    task_updates: TaskUpdate,
    user: User = Depends(get_current_user),
    _csrf: AuthSession = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    return task_service.update_task(db, task_id, user.id, task_updates)


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(
    task_id: str,
    user: User = Depends(get_current_user),
    _csrf: AuthSession = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    task_service.delete_task(db, task_id, user.id)
