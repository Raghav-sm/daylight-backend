from app.schemas.base import APIModel


class StageCreate(APIModel):
    name: str
    color: str


class StageRead(APIModel):
    id: str
    name: str
    color: str


class ProjectCreate(APIModel):
    name: str
    color: str = "blue"


class ProjectUpdate(APIModel):
    name: str | None = None
    color: str | None = None


class ProjectRead(APIModel):
    id: str
    name: str
    color: str
    stages: list[StageRead]
