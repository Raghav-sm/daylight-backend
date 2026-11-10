from __future__ import annotations

from uuid import uuid4

from sqlalchemy import ForeignKey, String, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Stage(Base):
    __tablename__ = "project_stages"
    __table_args__ = (UniqueConstraint("project_id", "name"),)

    id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("projects.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[str] = mapped_column(String(30), nullable=False)
    position: Mapped[int] = mapped_column(nullable=False, default=0)

    project: Mapped["Project"] = relationship(back_populates="stages")
    tasks: Mapped[list["Task"]] = relationship(back_populates="stage")
