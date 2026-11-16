from pydantic import Field, field_validator

from app.schemas.base import APIModel


class StageCreate(APIModel):
    name: str = Field(min_length=1, max_length=255)
    color: str = Field(min_length=1, max_length=50)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name cannot be blank")
        return stripped


class StageRead(APIModel):
    id: str
    name: str
    color: str


class ProjectCreate(APIModel):
    name: str = Field(min_length=1, max_length=255)
    color: str = Field(default="blue", min_length=1, max_length=50)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name cannot be blank")
        return stripped


class ProjectUpdate(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    color: str | None = Field(default=None, min_length=1, max_length=50)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("name cannot be blank")
        return stripped


class ProjectRead(APIModel):
    id: str
    name: str
    color: str
    stages: list[StageRead]


class ProjectSummary(APIModel):
    id: str
    name: str
    color: str
    task_count: int
    incomplete_task_count: int
    stage_count: int
