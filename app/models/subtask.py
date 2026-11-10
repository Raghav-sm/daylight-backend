from __future__ import annotations

from uuid import uuid4

from sqlalchemy import Boolean, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Subtask(Base):
    __tablename__ = "subtasks"

    id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    task_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    position: Mapped[int] = mapped_column(nullable=False, default=0)

    task: Mapped["Task"] = relationship(back_populates="subtasks")
