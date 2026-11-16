from datetime import date, datetime, time
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.base import APIModel


class SubtaskWrite(APIModel):
    id: str | None = None
    title: str = Field(min_length=1, max_length=255)
    completed: bool = False

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("title cannot be blank")
        return stripped

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            UUID(value)
        except ValueError as error:
            raise ValueError("id must be a valid UUID") from error
        return value


class SubtaskRead(APIModel):
    id: str
    title: str
    completed: bool


class TaskCreate(APIModel):
    title: str = Field(min_length=1, max_length=255)
    notes: str = ""
    due_date: date | None = None
    due_time: time | None = None
    priority: Literal["none", "low", "medium", "high"] = "none"
    stage_id: str | None = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("title cannot be blank")
        return stripped

    @model_validator(mode="after")
    def validate_due_pair(self):
        if self.due_time is not None and self.due_date is None:
            raise ValueError("due_time requires due_date")
        return self


class TaskUpdate(APIModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    notes: str | None = None
    project_id: str | None = None
    due_date: date | None = None
    due_time: time | None = None
    priority: Literal["none", "low", "medium", "high"] | None = None
    completed: bool | None = None
    stage_id: str | None = None
    subtasks: list[SubtaskWrite] | None = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("title cannot be blank")
        return stripped


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


class TaskSummary(APIModel):
    id: str
    project_id: str
    title: str
    due_date: date | None
    due_time: time | None
    priority: Literal["none", "low", "medium", "high"]
    completed: bool
    stage_id: str | None
    subtask_count: int
    completed_subtask_count: int
