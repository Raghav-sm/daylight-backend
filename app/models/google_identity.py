from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class GoogleIdentity(Base):
    __tablename__ = "google_identities"
    __table_args__ = (
        UniqueConstraint("provider", "subject", name="uq_google_identities_provider_subject"),
        UniqueConstraint("user_id", "provider", name="uq_google_identities_user_provider"),
    )

    id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="google")
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    email_at_link_time: Mapped[str] = mapped_column(String(254), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship(back_populates="google_identities")
