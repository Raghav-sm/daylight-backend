from __future__ import annotations

from uuid import uuid4

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    color: Mapped[str] = mapped_column(String(50), nullable=False, default="blue")

    stages: Mapped[list["Stage"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="Stage.position",
    )
    tasks: Mapped[list["Task"]] = relationship(back_populates="project")
