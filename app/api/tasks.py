from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.task import TaskCreate, TaskRead, TaskUpdate
from app.services import task_service

router = APIRouter(tags=["tasks"])


@router.post("/projects/{project_id}/tasks", status_code=201, response_model=TaskRead)
def create_task(
    project_id: str,
    task: TaskCreate,
    db: Session = Depends(get_db),
):
    return task_service.create_task(db, project_id, task)


@router.get("/tasks", status_code=200, response_model=list[TaskRead])
def get_tasks(db: Session = Depends(get_db)):
    return task_service.get_tasks(db)


@router.get(
    "/projects/{project_id}/tasks",
    status_code=200,
    response_model=list[TaskRead],
)
def get_project_tasks(project_id: str, db: Session = Depends(get_db)):
    return task_service.get_project_tasks(db, project_id)


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
