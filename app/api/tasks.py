from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.task import TaskRead, TaskUpdate
from app.services import task_service

router = APIRouter(tags=["tasks"])


@router.get("/tasks", status_code=200, response_model=list[TaskRead])
def get_tasks(db: Session = Depends(get_db)):
    """Legacy full task list. Prefer project-scoped summaries for the app."""
    return task_service.get_tasks(db)


@router.get("/tasks/{task_id}", status_code=200, response_model=TaskRead)
def get_task(task_id: str, db: Session = Depends(get_db)):
    return task_service.get_task(db, task_id)


@router.patch("/tasks/{task_id}", status_code=200, response_model=TaskRead)
def update_task(
    task_id: str,
    task_updates: TaskUpdate,
    db: Session = Depends(get_db),
):
    return task_service.update_task(db, task_id, task_updates)


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: str, db: Session = Depends(get_db)):
    task_service.delete_task(db, task_id)
