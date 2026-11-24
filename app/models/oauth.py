from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class OAuthAuthorizationRequest(Base):
    __tablename__ = "oauth_authorization_requests"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    handle_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    browser_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    client_id: Mapped[str] = mapped_column(String(2048), nullable=False)
    client_name: Mapped[str] = mapped_column(String(255), nullable=False)
    redirect_uri: Mapped[str] = mapped_column(String(2048), nullable=False)
    client_state: Mapped[str] = mapped_column(String(512), nullable=False)
    scopes: Mapped[list] = mapped_column(JSON, nullable=False)
    resource: Mapped[str] = mapped_column(String(2048), nullable=False)
    code_challenge: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OAuthGrant(Base):
    __tablename__ = "oauth_grants"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(String(2048), nullable=False)
    client_name: Mapped[str] = mapped_column(String(255), nullable=False)
    resource: Mapped[str] = mapped_column(String(2048), nullable=False)
    scopes: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OAuthCredential(Base):
    __tablename__ = "oauth_credentials"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    grant_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("oauth_grants.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    family_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), nullable=False, index=True)


class OAuthAuthorizationCode(Base):
    __tablename__ = "oauth_authorization_codes"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    request_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("oauth_authorization_requests.id", ondelete="CASCADE"), nullable=False)
    grant_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("oauth_grants.id", ondelete="CASCADE"), nullable=False)
    client_id: Mapped[str] = mapped_column(String(2048), nullable=False)
    redirect_uri: Mapped[str] = mapped_column(String(2048), nullable=False)
    resource: Mapped[str] = mapped_column(String(2048), nullable=False)
    scopes: Mapped[list] = mapped_column(JSON, nullable=False)
    code_challenge: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
