from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.config import SESSION_COOKIE_NAME, SESSION_COOKIE_SAMESITE, SESSION_COOKIE_SECURE
from app.database import get_db
from app.models import AuthSession, User
from app.schemas.auth import AuthResponse, Credentials, ProfileUpdate, RegistrationCredentials
from app.security.dependencies import (
    get_current_session,
    get_current_user,
    require_csrf,
    require_allowed_origin,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=auth_service.SESSION_MAX_AGE_SECONDS,
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite=SESSION_COOKIE_SAMESITE,
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=AuthResponse)
def register(
    credentials: RegistrationCredentials,
    response: Response,
    db: Session = Depends(get_db),
    _origin: None = Depends(require_allowed_origin),
):
    user, token, csrf_token = auth_service.register(db, credentials)
    _set_session_cookie(response, token)
    return {"user": user, "csrf_token": csrf_token}


@router.post("/login", response_model=AuthResponse)
def login(
    credentials: Credentials,
    response: Response,
    db: Session = Depends(get_db),
    _origin: None = Depends(require_allowed_origin),
):
    user, token, csrf_token = auth_service.login(db, credentials)
    _set_session_cookie(response, token)
    return {"user": user, "csrf_token": csrf_token}


@router.get("/me", response_model=AuthResponse)
def me(
    response: Response,
    user: User = Depends(get_current_user),
    auth_session: AuthSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    return {"user": user, "csrf_token": auth_session.csrf_token}


@router.patch("/me", response_model=AuthResponse)
def update_me(
    changes: ProfileUpdate,
    response: Response,
    user: User = Depends(get_current_user),
    _auth_session: AuthSession = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    updated_user = auth_service.update_profile(db, user, changes)
    response.headers["Cache-Control"] = "no-store"
    return {"user": updated_user, "csrf_token": _auth_session.csrf_token}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    auth_session: AuthSession = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    auth_service.logout(db, auth_session)
    response.status_code = status.HTTP_204_NO_CONTENT
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite=SESSION_COOKIE_SAMESITE,
    )
    response.headers["Cache-Control"] = "no-store"
    return response
