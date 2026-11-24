from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class GoogleLoginTransaction(Base):
    __tablename__ = "google_login_transactions"

    id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    state_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    browser_binding_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    nonce: Mapped[str] = mapped_column(String(128), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    return_path: Mapped[str] = mapped_column(String(255), nullable=False)
    oauth_request_handle: Mapped[str | None] = mapped_column(String(128), nullable=True)
    origin_page: Mapped[str] = mapped_column(String(32), nullable=False, default="login")
    linking_user_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
