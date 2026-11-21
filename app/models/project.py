from __future__ import annotations

from uuid import uuid4

from sqlalchemy import ForeignKey, String, Uuid
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
    initial_stage_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), nullable=True)
    final_stage_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), nullable=True)
    owner_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )

    owner: Mapped["User | None"] = relationship(back_populates="projects")
    stages: Mapped[list["Stage"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="Stage.position",
    )
    tasks: Mapped[list["Task"]] = relationship(back_populates="project")
