import os


def _read_origins() -> tuple[str, ...]:
    raw = os.getenv("FRONTEND_ORIGINS", "http://localhost:3000")
    return tuple(origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip())


FRONTEND_ORIGINS = _read_origins()
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "daylight_session")
SESSION_MAX_AGE_SECONDS = int(os.getenv("SESSION_MAX_AGE_SECONDS", str(7 * 24 * 60 * 60)))
SESSION_COOKIE_SECURE = os.getenv(
    "SESSION_COOKIE_SECURE",
    "true" if os.getenv("APP_ENV", "development").lower() == "production" else "false",
).lower() == "true"
