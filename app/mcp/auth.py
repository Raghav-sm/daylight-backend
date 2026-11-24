from datetime import datetime, timezone

from fastmcp.server.auth import AccessToken, TokenVerifier
from sqlalchemy import select

from app.config import BACKEND_PUBLIC_URL
from app.database import SessionLocal
from app.models import OAuthCredential, OAuthGrant, User
from app.security.dependencies import digest_token


RESOURCE_URL = f"{BACKEND_PUBLIC_URL}/mcp"


class DaylightTokenVerifier(TokenVerifier):
    """Verify opaque MCP bearer tokens against Daylight's grant store."""

    async def verify_token(self, token: str) -> AccessToken | None:
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            credential = db.scalar(
                select(OAuthCredential).where(
                    OAuthCredential.token_hash == digest_token(token),
                    OAuthCredential.kind == "access",
                    OAuthCredential.consumed_at.is_(None),
                    OAuthCredential.expires_at > now,
                )
            )
            if credential is None:
                return None
            grant = db.get(OAuthGrant, credential.grant_id)
            if grant is None or grant.revoked_at is not None or grant.resource != RESOURCE_URL:
                return None
            if db.get(User, grant.user_id) is None:
                return None
            return AccessToken(
                token=token,
                client_id=grant.client_id,
                scopes=list(credential.scopes),
                expires_at=int((credential.expires_at.replace(tzinfo=timezone.utc)
                                if credential.expires_at.tzinfo is None else credential.expires_at).timestamp()),
                resource=grant.resource,
                subject=grant.user_id,
                claims={"user_id": grant.user_id, "grant_id": grant.id},
            )
