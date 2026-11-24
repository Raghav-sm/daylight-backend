from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hmac
import logging
import secrets
import time
from urllib.parse import urlencode

from fastapi import HTTPException, status
import httpx
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet
from joserfc.jwt import JWTClaimsRegistry
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import (
    GOOGLE_TX_MAX_AGE_SECONDS,
    get_google_callback_url,
    get_google_client_id,
    get_google_client_secret,
    is_google_auth_configured,
)
from app.models import GoogleIdentity, GoogleLoginTransaction, User
from app.schemas.auth import GoogleAuthStatus
from app.security.dependencies import digest_token

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ["https://accounts.google.com", "accounts.google.com"]
logger = logging.getLogger(__name__)
GOOGLE_TOKEN_ERRORS = {"invalid_client", "invalid_grant", "invalid_request", "unauthorized_client", "unsupported_grant_type"}
ALLOWED_RETURN_PREFIXES = ("/dashboard", "/account", "/daylight", "/projects")
ALLOWED_ORIGIN_PAGES = {"login", "register", "account"}

_JWKS_CACHE_TTL_SECONDS = 3600
_jwks_cache: tuple[float, dict] | None = None


class GoogleAuthError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class GoogleVerifiedIdentity:
    sub: str
    email: str
    email_verified: bool
    name: str


def sanitize_return_path(raw: str | None, *, default: str = "/dashboard") -> str:
    if not raw:
        return default
    candidate = raw.strip()
    if not candidate.startswith("/") or candidate.startswith("//") or "\\" in candidate:
        return default
    if any(candidate == prefix or candidate.startswith(f"{prefix}/") for prefix in ALLOWED_RETURN_PREFIXES):
        return candidate
    return default


def sanitize_origin_page(raw: str | None, *, default: str = "login") -> str:
    if raw and raw.strip() in ALLOWED_ORIGIN_PAGES:
        return raw.strip()
    return default


def _normalize_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def fetch_google_jwks(*, force_refresh: bool = False) -> dict:
    global _jwks_cache
    now = time.monotonic()
    if not force_refresh and _jwks_cache is not None:
        fetched_at, cached = _jwks_cache
        if now - fetched_at < _JWKS_CACHE_TTL_SECONDS:
            return cached

    try:
        response = httpx.get(GOOGLE_JWKS_URL, timeout=10.0)
        response.raise_for_status()
        jwks = response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise GoogleAuthError("provider_error", "Could not verify Google signing keys.") from error

    if not isinstance(jwks, dict) or not isinstance(jwks.get("keys"), list):
        raise GoogleAuthError("provider_error", "Google signing keys response was invalid.")

    _jwks_cache = (now, jwks)
    return jwks


def exchange_code_for_id_token(code: str) -> str:
    client_id = get_google_client_id()
    client_secret = get_google_client_secret()
    if not client_id or not client_secret:
        raise GoogleAuthError("google_not_configured", "Google sign-in is not configured.")

    try:
        response = httpx.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": get_google_callback_url(),
                "grant_type": "authorization_code",
            },
            headers={"Accept": "application/json"},
            timeout=10.0,
        )
    except httpx.HTTPError as error:
        raise GoogleAuthError("provider_error", "Could not reach Google to finish sign-in.") from error

    if response.status_code != 200:
        try:
            error_code = response.json().get("error")
        except (ValueError, AttributeError):
            error_code = None
        safe_error = error_code if isinstance(error_code, str) and error_code in GOOGLE_TOKEN_ERRORS else "unknown"
        logger.warning("Google token exchange failed: status=%s error=%s", response.status_code, safe_error)
        raise GoogleAuthError("exchange_failed", "Google rejected the sign-in code. Please try again.")

    try:
        payload = response.json()
    except ValueError as error:
        logger.warning("Google token exchange returned non-JSON response: status=%s", response.status_code)
        raise GoogleAuthError("exchange_failed", "Invalid response from Google token endpoint.") from error

    id_token = payload.get("id_token")
    if not isinstance(id_token, str) or not id_token:
        logger.warning("Google token exchange response has no ID token: status=%s", response.status_code)
        raise GoogleAuthError("exchange_failed", "Google did not return an ID token.")
    return id_token


def verify_google_id_token(id_token: str, *, expected_nonce: str) -> GoogleVerifiedIdentity:
    client_id = get_google_client_id()
    if not client_id:
        raise GoogleAuthError("google_not_configured", "Google sign-in is not configured.")

    decoded = None
    last_error: Exception | None = None
    for force_refresh in (False, True):
        jwks = fetch_google_jwks(force_refresh=force_refresh)
        try:
            key_set = KeySet.import_key_set(jwks)
            decoded = jwt.decode(id_token, key_set, algorithms=["RS256"])
            break
        except (JoseError, ValueError) as error:
            last_error = error
            if force_refresh:
                break

    if decoded is None:
        raise GoogleAuthError("invalid_token", "Could not verify Google identity token.") from last_error

    claims_registry = JWTClaimsRegistry(
        iss={"essential": True, "values": GOOGLE_ISSUERS},
        aud={"essential": True, "value": client_id},
        sub={"essential": True},
        exp={"essential": True},
        nonce={"essential": True, "value": expected_nonce},
    )
    try:
        claims_registry.validate(decoded.claims)
    except JoseError as error:
        raise GoogleAuthError("invalid_token", "Google identity token failed validation.") from error

    claims = decoded.claims
    sub = claims.get("sub")
    raw_email = claims.get("email")
    email_verified = claims.get("email_verified") is True
    raw_name = claims.get("name")

    if not isinstance(sub, str) or not sub.strip():
        raise GoogleAuthError("invalid_token", "Google identity token is missing a subject.")
    if not isinstance(raw_email, str) or not raw_email.strip():
        raise GoogleAuthError("email_required", "Google did not provide an email address.")

    email = raw_email.strip().casefold()
    fallback_name = email.split("@", 1)[0] or "Daylight user"
    name = " ".join(raw_name.split())[:100] if isinstance(raw_name, str) and raw_name.strip() else fallback_name[:100]

    return GoogleVerifiedIdentity(
        sub=sub.strip(),
        email=email,
        email_verified=email_verified,
        name=name,
    )


def start_google_transaction(
    db: Session,
    *,
    mode: str,
    return_path: str,
    origin_page: str,
    linking_user_id: str | None = None,
    oauth_request_handle: str | None = None,
) -> tuple[str, str]:
    if not is_google_auth_configured():
        raise GoogleAuthError("google_not_configured", "Google sign-in is not configured on this server.")

    raw_state = secrets.token_urlsafe(32)
    raw_nonce = secrets.token_urlsafe(32)
    raw_browser_binding = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)

    transaction = GoogleLoginTransaction(
        state_hash=digest_token(raw_state),
        browser_binding_hash=digest_token(raw_browser_binding),
        nonce=raw_nonce,
        mode=mode,
        return_path=sanitize_return_path(return_path, default="/account" if mode == "link" else "/dashboard"),
        origin_page=sanitize_origin_page(origin_page, default="account" if mode == "link" else "login"),
        linking_user_id=linking_user_id,
        oauth_request_handle=oauth_request_handle,
        expires_at=now + timedelta(seconds=GOOGLE_TX_MAX_AGE_SECONDS),
        created_at=now,
    )
    db.add(transaction)
    db.commit()

    params = {
        "client_id": get_google_client_id(),
        "redirect_uri": get_google_callback_url(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": raw_state,
        "nonce": raw_nonce,
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}", raw_browser_binding


def consume_google_transaction(
    db: Session,
    *,
    state: str | None,
    raw_browser_binding: str | None,
) -> GoogleLoginTransaction:
    if not state or not raw_browser_binding:
        raise GoogleAuthError("invalid_state", "Google sign-in session could not be verified. Please try again.")

    transaction = db.scalar(
        select(GoogleLoginTransaction).where(
            GoogleLoginTransaction.state_hash == digest_token(state)
        )
    )
    if transaction is None:
        raise GoogleAuthError("invalid_state", "Google sign-in session was not found. Please try again.")

    if transaction.consumed_at is not None:
        raise GoogleAuthError("invalid_state", "This Google sign-in attempt was already used. Please try again.")

    now = datetime.now(timezone.utc)
    if _normalize_utc(transaction.expires_at) <= now:
        transaction.consumed_at = now
        db.commit()
        raise GoogleAuthError("expired", "Your Google sign-in attempt expired. Please try again.")

    expected_binding = transaction.browser_binding_hash
    actual_binding = digest_token(raw_browser_binding)
    if not hmac.compare_digest(expected_binding, actual_binding):
        raise GoogleAuthError("invalid_state", "Google sign-in must finish in the same browser that started it.")

    transaction.consumed_at = now
    db.commit()
    return transaction


def resolve_google_login(db: Session, identity: GoogleVerifiedIdentity) -> User:
    linked = db.scalar(
        select(GoogleIdentity).where(
            GoogleIdentity.provider == "google",
            GoogleIdentity.subject == identity.sub,
        )
    )
    if linked is not None:
        user = db.get(User, linked.user_id)
        if user is None:
            raise GoogleAuthError("provider_error", "Linked Daylight user could not be found.")
        return user

    if not identity.email_verified:
        raise GoogleAuthError(
            "unverified_email",
            "Your Google account email must be verified before creating a Daylight account.",
        )

    existing_user = db.scalar(select(User).where(User.email == identity.email))
    if existing_user is not None:
        raise GoogleAuthError(
            "account_exists",
            "An account with this email already exists. Sign in with your password, then link Google in Account.",
        )

    user = User(
        name=identity.name,
        email=identity.email,
        password_hash=None,
    )
    db.add(user)
    try:
        db.flush()
        db.add(
            GoogleIdentity(
                user_id=user.id,
                provider="google",
                subject=identity.sub,
                email_at_link_time=identity.email,
            )
        )
        db.flush()
    except IntegrityError:
        db.rollback()
        # Handle concurrent login race for the same Google subject or email.
        linked = db.scalar(
            select(GoogleIdentity).where(
                GoogleIdentity.provider == "google",
                GoogleIdentity.subject == identity.sub,
            )
        )
        if linked is not None:
            user = db.get(User, linked.user_id)
            if user is not None:
                return user
        raise GoogleAuthError(
            "account_exists",
            "An account with this email already exists. Sign in with your password, then link Google in Account.",
        ) from None

    return user


def complete_google_link(db: Session, *, user: User, identity: GoogleVerifiedIdentity) -> GoogleIdentity:
    existing_subject = db.scalar(
        select(GoogleIdentity).where(
            GoogleIdentity.provider == "google",
            GoogleIdentity.subject == identity.sub,
        )
    )
    if existing_subject is not None:
        if existing_subject.user_id == user.id:
            return existing_subject
        raise GoogleAuthError(
            "already_linked",
            "That Google account is already linked to another Daylight user.",
        )

    existing_for_user = db.scalar(
        select(GoogleIdentity).where(
            GoogleIdentity.user_id == user.id,
            GoogleIdentity.provider == "google",
        )
    )
    if existing_for_user is not None:
        raise GoogleAuthError(
            "user_already_linked",
            "Your Daylight account is already linked to a Google account.",
        )

    link = GoogleIdentity(
        user_id=user.id,
        provider="google",
        subject=identity.sub,
        email_at_link_time=identity.email,
    )
    db.add(link)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise GoogleAuthError(
            "already_linked",
            "That Google account is already linked to another Daylight user.",
        ) from None
    db.refresh(link)
    return link


def get_google_status(db: Session, user: User) -> GoogleAuthStatus:
    linked = db.scalar(
        select(GoogleIdentity).where(
            GoogleIdentity.user_id == user.id,
            GoogleIdentity.provider == "google",
        )
    )
    has_password = bool(user.password_hash)
    return GoogleAuthStatus(
        configured=is_google_auth_configured(),
        linked=linked is not None,
        linked_email=linked.email_at_link_time if linked is not None else None,
        has_password=has_password,
        can_unlink=bool(linked is not None and has_password),
    )


def unlink_google_identity(db: Session, user: User) -> None:
    linked = db.scalar(
        select(GoogleIdentity).where(
            GoogleIdentity.user_id == user.id,
            GoogleIdentity.provider == "google",
        )
    )
    if linked is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Google account is linked.")
    if not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot unlink Google because this account does not have a password.",
        )
    db.delete(linked)
    db.commit()
