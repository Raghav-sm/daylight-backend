from datetime import date, datetime, time
from typing import Literal

from app.schemas.base import APIModel


class SubtaskWrite(APIModel):
    id: str | None = None
    title: str
    completed: bool = False


class SubtaskRead(APIModel):
    id: str
    title: str
    completed: bool


class TaskCreate(APIModel):
    title: str
    notes: str = ""
    due_date: date | None = None
    due_time: time | None = None
    priority: Literal["none", "low", "medium", "high"] = "none"
    stage_id: str | None = None


class TaskUpdate(APIModel):
    title: str | None = None
    notes: str | None = None
    project_id: str | None = None
    due_date: date | None = None
    due_time: time | None = None
    priority: Literal["none", "low", "medium", "high"] | None = None
    completed: bool | None = None
    stage_id: str | None = None
    subtasks: list[SubtaskWrite] | None = None


class TaskRead(APIModel):
    id: str
    project_id: str
    title: str
    notes: str
    due_date: date | None
    due_time: time | None
    priority: Literal["none", "low", "medium", "high"]
    completed: bool
    completed_at: datetime | None
    created_at: datetime
    stage_id: str | None
    subtasks: list[SubtaskRead]
