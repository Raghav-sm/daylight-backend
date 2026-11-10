from __future__ import annotations

from datetime import date, datetime, time, timezone
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, Time, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Task(Base):
    __tablename__ = "tasks"

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
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
    completed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    stage_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("project_stages.id"),
        nullable=True,
        index=True,
    )

    project: Mapped["Project"] = relationship(back_populates="tasks")
    stage: Mapped["Stage | None"] = relationship(back_populates="tasks")
    subtasks: Mapped[list["Subtask"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="Subtask.position",
    )
