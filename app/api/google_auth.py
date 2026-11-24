from urllib.parse import urlencode
from datetime import datetime, timezone
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import _set_session_cookie
from app.config import (
    BACKEND_PUBLIC_URL,
    FRONTEND_PUBLIC_URL,
    GOOGLE_TX_COOKIE_NAME,
    GOOGLE_TX_MAX_AGE_SECONDS,
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_SECURE,
)
from app.database import get_db
from app.models import AuthSession, OAuthAuthorizationRequest, User
from app.schemas.auth import GoogleAuthStatus, GoogleLinkStartResponse
from app.security.dependencies import digest_token, get_current_user, require_csrf
from app.services import auth_service, google_auth_service
from app.services.google_auth_service import GoogleAuthError

router = APIRouter(prefix="/auth/google", tags=["auth"])


def _set_tx_cookie(response: Response, raw_binding: str) -> None:
    response.set_cookie(
        key=GOOGLE_TX_COOKIE_NAME,
        value=raw_binding,
        max_age=GOOGLE_TX_MAX_AGE_SECONDS,
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite="lax",
        path="/auth/google",
    )
    response.headers["Cache-Control"] = "no-store"


def _clear_tx_cookie(response: Response) -> None:
    response.delete_cookie(
        key=GOOGLE_TX_COOKIE_NAME,
        path="/auth/google",
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite="lax",
    )
    response.headers["Cache-Control"] = "no-store"


def _frontend_error_redirect(origin_page: str, error_code: str) -> RedirectResponse:
    target_path = {
        "register": "/register",
        "account": "/account",
    }.get(origin_page, "/login")
    query = urlencode({"google_error": error_code})
    response = RedirectResponse(
        url=f"{FRONTEND_PUBLIC_URL}{target_path}?{query}",
        status_code=status.HTTP_302_FOUND,
    )
    _clear_tx_cookie(response)
    return response


def _current_session_user_id(request: Request, db: Session) -> str | None:
    raw_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw_token:
        return None
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == digest_token(raw_token)))
    if session is None:
        return None
    expires_at = google_auth_service._normalize_utc(session.expires_at)
    from datetime import datetime, timezone

    if expires_at <= datetime.now(timezone.utc):
        return None
    return session.user_id


@router.get("/start")
def google_login_start(
    request: Request,
    return_to: str | None = Query(default="/dashboard"),
    origin_page: str | None = Query(default="login"),
    oauth_continue: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    safe_origin = google_auth_service.sanitize_origin_page(origin_page, default="login")
    safe_return = google_auth_service.sanitize_return_path(return_to, default="/dashboard")
    if oauth_continue:
        pending = db.scalar(select(OAuthAuthorizationRequest).where(
            OAuthAuthorizationRequest.handle_hash == digest_token(oauth_continue)
        ))
        binding = request.cookies.get("daylight_oauth_binding", "")
        if (pending is None or pending.consumed_at is not None or google_auth_service._normalize_utc(pending.expires_at) <= datetime.now(timezone.utc)
                or not binding or not secrets.compare_digest(pending.browser_hash, digest_token(binding))):
            raise HTTPException(status_code=400, detail="Authorization request expired. Restart the connection from Claude.")
    try:
        auth_url, raw_binding = google_auth_service.start_google_transaction(
            db,
            mode="login",
            return_path=safe_return,
            origin_page=safe_origin,
            oauth_request_handle=oauth_continue,
        )
    except GoogleAuthError as error:
        return _frontend_error_redirect(safe_origin, error.code)

    response = RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)
    _set_tx_cookie(response, raw_binding)
    return response


@router.post("/link/start", response_model=GoogleLinkStartResponse)
def google_link_start(
    response: Response,
    user: User = Depends(get_current_user),
    _csrf: AuthSession = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> GoogleLinkStartResponse:
    try:
        auth_url, raw_binding = google_auth_service.start_google_transaction(
            db,
            mode="link",
            return_path="/account",
            origin_page="account",
            linking_user_id=user.id,
        )
    except GoogleAuthError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=error.message) from None

    _set_tx_cookie(response, raw_binding)
    return GoogleLinkStartResponse(authorization_url=auth_url)


@router.get("/callback")
def google_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    raw_binding = request.cookies.get(GOOGLE_TX_COOKIE_NAME)
    origin_page = "login"

    try:
        transaction = google_auth_service.consume_google_transaction(
            db,
            state=state,
            raw_browser_binding=raw_binding,
        )
        origin_page = transaction.origin_page
    except GoogleAuthError as auth_error:
        return _frontend_error_redirect(origin_page, auth_error.code)

    if error:
        error_code = "cancelled" if error == "access_denied" else "provider_error"
        return _frontend_error_redirect(origin_page, error_code)

    if not code:
        return _frontend_error_redirect(origin_page, "provider_error")

    try:
        id_token = google_auth_service.exchange_code_for_id_token(code)
        identity = google_auth_service.verify_google_id_token(id_token, expected_nonce=transaction.nonce)
    except GoogleAuthError as auth_error:
        return _frontend_error_redirect(origin_page, auth_error.code)

    if transaction.mode == "link":
        active_user_id = _current_session_user_id(request, db)
        if not active_user_id or active_user_id != transaction.linking_user_id:
            return _frontend_error_redirect("account", "session_mismatch")
        user = db.get(User, active_user_id)
        if user is None:
            return _frontend_error_redirect("account", "session_mismatch")
        try:
            google_auth_service.complete_google_link(db, user=user, identity=identity)
        except GoogleAuthError as auth_error:
            return _frontend_error_redirect("account", auth_error.code)

        response = RedirectResponse(
            url=f"{FRONTEND_PUBLIC_URL}/account?google=linked",
            status_code=status.HTTP_302_FOUND,
        )
        _clear_tx_cookie(response)
        return response

    try:
        user = google_auth_service.resolve_google_login(db, identity)
    except GoogleAuthError as auth_error:
        return _frontend_error_redirect(origin_page, auth_error.code)

    _, raw_session_token, _csrf_token = auth_service._create_session(db, user)
    db.commit()

    destination = (f"{BACKEND_PUBLIC_URL}/oauth/continue?{urlencode({'request': transaction.oauth_request_handle})}"
                   if transaction.oauth_request_handle else f"{FRONTEND_PUBLIC_URL}{transaction.return_path}")
    response = RedirectResponse(
        url=destination,
        status_code=status.HTTP_302_FOUND,
    )
    _set_session_cookie(response, raw_session_token)
    _clear_tx_cookie(response)
    return response


@router.get("/status", response_model=GoogleAuthStatus)
def google_status(
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GoogleAuthStatus:
    response.headers["Cache-Control"] = "no-store"
    return google_auth_service.get_google_status(db, user)


@router.delete("/link", status_code=status.HTTP_204_NO_CONTENT)
def google_unlink(
    response: Response,
    user: User = Depends(get_current_user),
    _csrf: AuthSession = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    google_auth_service.unlink_google_identity(db, user)
    response.headers["Cache-Control"] = "no-store"
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers={"Cache-Control": "no-store"})
