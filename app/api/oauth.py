from __future__ import annotations

from datetime import datetime, timedelta, timezone
import base64
import html
import hashlib
import ipaddress
import secrets
from urllib.parse import urlencode, urlparse
import socket
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.security.dependencies import get_current_user, require_csrf

from app.config import BACKEND_PUBLIC_URL, FRONTEND_PUBLIC_URL, SESSION_COOKIE_NAME
from app.database import get_db
from app.models import (
    AuthSession, OAuthAuthorizationCode, OAuthAuthorizationRequest,
    OAuthCredential, OAuthGrant, User,
)
from app.security.dependencies import digest_token

router = APIRouter(tags=["oauth"])
RESOURCE = f"{BACKEND_PUBLIC_URL}/mcp"
BINDING_COOKIE = "daylight_oauth_binding"
SUPPORTED_SCOPES = {"daylight:read", "daylight:write"}
AUTH_TTL = 600
ACCESS_TTL = 900
REFRESH_TTL = 60 * 60 * 24 * 30


def _token(db: Session, grant: OAuthGrant, kind: str, expires: int,
           scopes: list[str], family: str | None = None) -> str:
    value = secrets.token_urlsafe(48)
    db.add(OAuthCredential(token_hash=digest_token(value), grant_id=grant.id, kind=kind, scopes=list(scopes),
        expires_at=_now()+timedelta(seconds=expires), family_id=family or str(uuid4())))
    return value


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _active_user(request: Request, db: Session) -> User | None:
    raw = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw:
        return None
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == digest_token(raw)))
    if session is None or _utc(session.expires_at) <= _now():
        return None
    return db.get(User, session.user_id)


def _pending(db: Session, handle: str, request: Request) -> OAuthAuthorizationRequest:
    row = db.scalar(select(OAuthAuthorizationRequest).where(
        OAuthAuthorizationRequest.handle_hash == digest_token(handle)
    ))
    binding = request.cookies.get(BINDING_COOKIE, "")
    if (row is None or row.consumed_at is not None or _utc(row.expires_at) <= _now()
            or not secrets.compare_digest(row.browser_hash, digest_token(binding))):
        raise HTTPException(400, "Authorization request expired. Restart the connection from Claude.")
    return row


async def _client_metadata(client_id: str) -> tuple[str, list[str]]:
    parsed = urlparse(client_id)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise HTTPException(400, "client_id must be an HTTPS Client ID Metadata URL")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
            raise ValueError("non-public host")
        async with httpx.AsyncClient(timeout=4, follow_redirects=False) as client:
            response = await client.get(client_id, headers={"Accept": "application/json"})
        if response.status_code != 200 or len(response.content) > 65536:
            raise ValueError("metadata fetch failed")
        metadata = response.json()
        if metadata.get("client_id") != client_id or not isinstance(metadata.get("redirect_uris"), list):
            raise ValueError("invalid metadata")
        name = str(metadata.get("client_name") or "MCP client")[:255]
        redirects = metadata["redirect_uris"]
        if not redirects or any(not isinstance(uri, str) or len(uri) > 2048 for uri in redirects):
            raise ValueError("invalid redirect URI")
        return name, redirects
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, "Could not validate the OAuth client metadata") from exc


@router.get("/.well-known/oauth-authorization-server")
def authorization_server_metadata():
    return {
        "issuer": BACKEND_PUBLIC_URL,
        "authorization_endpoint": f"{BACKEND_PUBLIC_URL}/oauth/authorize",
        "token_endpoint": f"{BACKEND_PUBLIC_URL}/oauth/token",
        "revocation_endpoint": f"{BACKEND_PUBLIC_URL}/oauth/revoke",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "scopes_supported": sorted(SUPPORTED_SCOPES),
        "client_id_metadata_document_supported": True,
    }


@router.get("/oauth/authorize")
async def authorize(request: Request, response: Response, client_id: str, redirect_uri: str,
                    scope: str = "daylight:read daylight:write", state: str = "",
                    response_type: str = "code", code_challenge: str = "",
                    code_challenge_method: str = "S256", resource: str = "",
                    db: Session = Depends(get_db)):
    if response_type != "code" or not state or len(state) > 512 or not code_challenge or code_challenge_method != "S256":
        raise HTTPException(400, "Invalid OAuth authorization request")
    if resource != RESOURCE:
        raise HTTPException(400, "Invalid resource")
    scopes = scope.split()
    if not scopes or len(scopes) != len(set(scopes)) or not set(scopes) <= SUPPORTED_SCOPES:
        raise HTTPException(400, "Unsupported scope")
    client_name, redirects = await _client_metadata(client_id)
    if redirect_uri not in redirects:
        raise HTTPException(400, "redirect_uri is not registered for this client")
    handle = secrets.token_urlsafe(32)
    binding = request.cookies.get(BINDING_COOKIE) or secrets.token_urlsafe(32)
    row = OAuthAuthorizationRequest(
        handle_hash=digest_token(handle), browser_hash=digest_token(binding), client_id=client_id,
        client_name=client_name, redirect_uri=redirect_uri, client_state=state, scopes=scopes,
        resource=resource, code_challenge=code_challenge, expires_at=_now()+timedelta(seconds=AUTH_TTL),
    )
    db.add(row); db.commit()
    response = RedirectResponse(f"{FRONTEND_PUBLIC_URL}/login?oauth_continue={handle}", status_code=303)
    if _active_user(request, db):
        response = RedirectResponse(f"{BACKEND_PUBLIC_URL}/oauth/continue?request={handle}", status_code=303)
    response.set_cookie(BINDING_COOKIE, binding, max_age=AUTH_TTL, httponly=True,
                        secure=BACKEND_PUBLIC_URL.startswith("https://"), samesite="lax", path="/")
    return response


@router.get("/oauth/continue", response_class=HTMLResponse)
def continue_authorization(request: Request, request_handle: str = Query(alias="request"), db: Session = Depends(get_db)):
    row = _pending(db, request_handle, request)
    user = _active_user(request, db)
    if user is None:
        return RedirectResponse(f"{FRONTEND_PUBLIC_URL}/login?oauth_continue={request_handle}", status_code=303)
    scopes = " and ".join("read your projects and tasks" if s == "daylight:read" else "create and move tasks" for s in row.scopes)
    session = db.scalar(select(AuthSession).where(
        AuthSession.token_hash == digest_token(request.cookies.get(SESSION_COOKIE_NAME, "")),
        AuthSession.expires_at > _now(),
    ))
    parsed_redirect = urlparse(row.redirect_uri)
    redirect_origin = (
        f"{parsed_redirect.scheme}://{parsed_redirect.netloc}"
        if parsed_redirect.scheme and parsed_redirect.netloc
        else ""
    )
    form_action = (
        f"'self' {redirect_origin}"
        if redirect_origin and not any(ch.isspace() or ch == ";" for ch in redirect_origin)
        else "'self'"
    )
    body = f'''<!doctype html><title>Connect Daylight</title><main style="font:16px system-ui;max-width:520px;margin:10vh auto;padding:24px"><h1>Connect {html.escape(row.client_name)} to Daylight?</h1><p>Signed in as <b>{html.escape(user.email)}</b>.</p><p>This connector can {html.escape(scopes)}.</p><form method="post" action="/oauth/authorize/decision"><input type="hidden" name="request" value="{html.escape(request_handle, quote=True)}"><input type="hidden" name="csrf" value="{html.escape(session.csrf_token if session else '', quote=True)}"><button name="decision" value="approve">Approve</button> <button name="decision" value="deny">Deny</button></form></main>'''
    return HTMLResponse(
        body,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": (
                f"default-src 'none'; style-src 'unsafe-inline'; form-action {form_action}; "
                "base-uri 'none'; frame-ancestors 'none'"
            ),
        },
    )


@router.post("/oauth/authorize/decision")
def authorization_decision(request: Request, handle: str = Form(alias="request"), csrf: str = Form(),
                           decision: str = Form(), db: Session = Depends(get_db)):
    origin = request.headers.get("origin", "").rstrip("/")
    if origin != BACKEND_PUBLIC_URL:
        raise HTTPException(403, "Request origin is not allowed")
    row = _pending(db, handle, request)
    user = _active_user(request, db)
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == digest_token(request.cookies.get(SESSION_COOKIE_NAME, ""))))
    if user is None or session is None or not secrets.compare_digest(session.csrf_token, csrf):
        raise HTTPException(403, "Sign in again to approve this connection")
    if decision == "deny":
        row.consumed_at = _now(); db.commit()
        target = row.redirect_uri + ("&" if "?" in row.redirect_uri else "?") + urlencode({"error":"access_denied", "state":row.client_state})
        return RedirectResponse(target, status_code=303)
    if decision != "approve": raise HTTPException(400, "Invalid decision")
    grant = db.scalar(select(OAuthGrant).where(OAuthGrant.user_id == user.id, OAuthGrant.client_id == row.client_id, OAuthGrant.resource == row.resource, OAuthGrant.revoked_at.is_(None)))
    if grant is None:
        grant = OAuthGrant(user_id=user.id, client_id=row.client_id, client_name=row.client_name, resource=row.resource, scopes=row.scopes)
        db.add(grant); db.flush()
    else:
        grant.scopes = sorted(set(grant.scopes) | set(row.scopes))
    code = secrets.token_urlsafe(32)
    db.add(OAuthAuthorizationCode(code_hash=digest_token(code), request_id=row.id, grant_id=grant.id,
        client_id=row.client_id, redirect_uri=row.redirect_uri, resource=row.resource, scopes=row.scopes,
        code_challenge=row.code_challenge, expires_at=_now()+timedelta(minutes=2)))
    row.consumed_at = _now(); db.commit()
    target = row.redirect_uri + ("&" if "?" in row.redirect_uri else "?") + urlencode({"code":code, "state":row.client_state})
    return RedirectResponse(target, status_code=303)


@router.post("/oauth/token")
def token(response: Response, grant_type: str = Form(), client_id: str = Form(),
          code: str | None = Form(default=None), redirect_uri: str | None = Form(default=None),
          code_verifier: str | None = Form(default=None), refresh_token: str | None = Form(default=None),
          resource: str = Form(), db: Session = Depends(get_db)):
    if resource != RESOURCE:
        return JSONResponse({"error":"invalid_target"}, status_code=400, headers={"Cache-Control":"no-store"})
    if grant_type == "authorization_code":
        row = db.scalar(select(OAuthAuthorizationCode).where(OAuthAuthorizationCode.code_hash == digest_token(code or "")).with_for_update())
        if (row is None or row.used_at is not None or _utc(row.expires_at) <= _now() or row.client_id != client_id
                or row.redirect_uri != redirect_uri or row.resource != resource or not code_verifier):
            return JSONResponse({"error":"invalid_grant"}, status_code=400, headers={"Cache-Control":"no-store"})
        verifier_hash = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b"=").decode()
        if not secrets.compare_digest(verifier_hash, row.code_challenge):
            return JSONResponse({"error":"invalid_grant"}, status_code=400, headers={"Cache-Control":"no-store"})
        grant = db.get(OAuthGrant, row.grant_id)
        if grant is None or grant.revoked_at is not None:
            return JSONResponse({"error":"invalid_grant"}, status_code=400, headers={"Cache-Control":"no-store"})
        row.used_at = _now()
        family = str(uuid4())
        issued_scopes = list(row.scopes)
    elif grant_type == "refresh_token":
        cred = db.scalar(select(OAuthCredential).where(OAuthCredential.token_hash == digest_token(refresh_token or ""), OAuthCredential.kind == "refresh").with_for_update())
        if cred is None or _utc(cred.expires_at) <= _now() or cred.consumed_at is not None:
            if cred is not None:
                db.query(OAuthCredential).filter(OAuthCredential.family_id == cred.family_id).update({"consumed_at": _now()})
            db.commit()
            return JSONResponse({"error":"invalid_grant"}, status_code=400, headers={"Cache-Control":"no-store"})
        grant = db.get(OAuthGrant, cred.grant_id)
        if grant is None or grant.revoked_at is not None or grant.client_id != client_id:
            return JSONResponse({"error":"invalid_grant"}, status_code=400, headers={"Cache-Control":"no-store"})
        cred.consumed_at = _now(); family = cred.family_id
        issued_scopes = list(cred.scopes)
    else:
        return JSONResponse({"error":"unsupported_grant_type"}, status_code=400, headers={"Cache-Control":"no-store"})
    access = _token(db, grant, "access", ACCESS_TTL, issued_scopes, family)
    refresh = _token(db, grant, "refresh", REFRESH_TTL, issued_scopes, family)
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return {"access_token":access, "token_type":"Bearer", "expires_in":ACCESS_TTL,
            "refresh_token":refresh, "scope":" ".join(issued_scopes)}


@router.post("/oauth/revoke")
def revoke(token: str = Form(), client_id: str = Form(), db: Session = Depends(get_db)):
    cred = db.scalar(select(OAuthCredential).where(OAuthCredential.token_hash == digest_token(token)))
    if cred is not None:
        grant = db.get(OAuthGrant, cred.grant_id)
        if grant and grant.client_id == client_id:
            grant.revoked_at = _now()
            db.commit()
    return Response(status_code=200, headers={"Cache-Control":"no-store"})


@router.get("/auth/connected-apps")
def connected_apps(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    grants = db.scalars(select(OAuthGrant).where(
        OAuthGrant.user_id == user.id, OAuthGrant.revoked_at.is_(None)
    ).order_by(OAuthGrant.created_at.desc())).all()
    return [{"id": g.id, "name": g.client_name, "scopes": g.scopes, "createdAt": g.created_at}
            for g in grants]


@router.delete("/auth/connected-apps/{grant_id}", status_code=204)
def disconnect_app(grant_id: str, user: User = Depends(get_current_user),
                   _csrf=Depends(require_csrf), db: Session = Depends(get_db)):
    grant = db.scalar(select(OAuthGrant).where(OAuthGrant.id == grant_id, OAuthGrant.user_id == user.id))
    if grant is None:
        raise HTTPException(404, "Connected app not found")
    grant.revoked_at = _now()
    db.commit()
    return Response(status_code=204, headers={"Cache-Control":"no-store"})
