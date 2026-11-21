from datetime import datetime, timedelta, timezone
import secrets

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import SESSION_MAX_AGE_SECONDS
from app.models import AuthSession, User
from app.schemas.auth import Credentials, ProfileUpdate, RegistrationCredentials
from app.security.dependencies import digest_token
from app.security.passwords import hash_password, verify_password


def _create_session(db: Session, user: User) -> tuple[AuthSession, str, str]:
    raw_token = secrets.token_urlsafe(32) 
    csrf_token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    auth_session = AuthSession(
        user_id=user.id,
        token_hash=digest_token(raw_token),
        csrf_token=csrf_token,
        created_at=now,
        expires_at=now + timedelta(seconds=SESSION_MAX_AGE_SECONDS),
    )
    db.add(auth_session)
    return auth_session, raw_token, csrf_token


def register(db: Session, credentials: RegistrationCredentials) -> tuple[User, str, str]:
    user = User(
        name=credentials.name,
        email=credentials.email,
        password_hash=hash_password(credentials.password),
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with that email already exists") from None
    _, raw_token, csrf_token = _create_session(db, user)
    db.commit()
    db.refresh(user)
    return user, raw_token, csrf_token


def login(db: Session, credentials: Credentials) -> tuple[User, str, str]:
    user = db.scalar(select(User).where(User.email == credentials.email))
    if user is None or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    _, raw_token, csrf_token = _create_session(db, user)
    db.commit()
    return user, raw_token, csrf_token


def update_profile(db: Session, user: User, changes: ProfileUpdate) -> User:
    user.name = changes.name
    db.commit()
    db.refresh(user)
    return user


def logout(db: Session, auth_session: AuthSession) -> None:
    db.delete(auth_session)
    db.commit()
