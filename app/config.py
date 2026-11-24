import os
from typing import Literal


def _read_origins() -> tuple[str, ...]:
    raw = os.getenv("FRONTEND_ORIGINS", "http://localhost:3000")
    return tuple(origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip())


def _read_cookie_samesite() -> Literal["lax", "strict", "none"]:
    raw = os.getenv("SESSION_COOKIE_SAMESITE", "lax").strip().lower()
    if raw == "lax":
        return "lax"
    if raw == "strict":
        return "strict"
    if raw == "none":
        return "none"
    raise ValueError("SESSION_COOKIE_SAMESITE must be 'lax', 'strict', or 'none'")


FRONTEND_ORIGINS = _read_origins()
FRONTEND_PUBLIC_URL = os.getenv(
    "FRONTEND_PUBLIC_URL",
    FRONTEND_ORIGINS[0] if FRONTEND_ORIGINS else "http://localhost:3000",
).strip().rstrip("/")
BACKEND_PUBLIC_URL = os.getenv("BACKEND_PUBLIC_URL", "http://localhost:8000").strip().rstrip("/")
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "daylight_session")
SESSION_MAX_AGE_SECONDS = int(os.getenv("SESSION_MAX_AGE_SECONDS", str(7 * 24 * 60 * 60)))
SESSION_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = _read_cookie_samesite()
SESSION_COOKIE_SECURE = os.getenv(
    "SESSION_COOKIE_SECURE",
    "true"
    if (os.getenv("APP_ENV", "development").lower() == "production" or SESSION_COOKIE_SAMESITE == "none")
    else "false",
).lower() == "true"
if SESSION_COOKIE_SAMESITE == "none" and not SESSION_COOKIE_SECURE:
    raise ValueError("SESSION_COOKIE_SECURE must be true when SESSION_COOKIE_SAMESITE is 'none'")
GOOGLE_TX_COOKIE_NAME = os.getenv("GOOGLE_TX_COOKIE_NAME", "daylight_google_tx")
GOOGLE_TX_MAX_AGE_SECONDS = int(os.getenv("GOOGLE_TX_MAX_AGE_SECONDS", "600"))


def get_google_client_id() -> str:
    return os.getenv("GOOGLE_CLIENT_ID", "").strip()


def get_google_client_secret() -> str:
    return os.getenv("GOOGLE_CLIENT_SECRET", "").strip()


def get_google_callback_url() -> str:
    override = os.getenv("GOOGLE_CALLBACK_URL", "").strip()
    if override:
        return override
    return f"{BACKEND_PUBLIC_URL}/auth/google/callback"


def is_google_auth_configured() -> bool:
    return bool(get_google_client_id() and get_google_client_secret())
