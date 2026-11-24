import asyncio
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from uuid import uuid4
from urllib.parse import parse_qs, urlparse

from sqlalchemy.orm import Session, sessionmaker

from app.mcp import auth as mcp_auth
from app.models import OAuthCredential, OAuthGrant, User
from app.models import OAuthAuthorizationRequest
from app.services.auth_service import _create_session
from app.security.dependencies import digest_token
from app.api import oauth


def test_mcp_discovery_uses_canonical_resource(client):
    metadata = client.get("/.well-known/oauth-protected-resource/mcp")
    assert metadata.status_code == 200
    assert metadata.json()["resource"] == "http://localhost:8000/mcp"

    response = client.post("/mcp", follow_redirects=False)
    assert response.status_code == 401
    assert response.headers.get("location") is None
    assert 'resource_metadata="http://localhost:8000/.well-known/oauth-protected-resource/mcp"' in response.headers["www-authenticate"]


def test_access_token_keeps_issued_scopes_when_grant_changes(db_engine, monkeypatch):
    raw = secrets.token_urlsafe(32)
    with Session(db_engine) as db:
        user = User(name="MCP User", email="mcp@example.com", password_hash=None)
        db.add(user)
        db.flush()
        grant = OAuthGrant(user_id=user.id, client_id="https://claude.ai/client.json", client_name="Claude",
                           resource=mcp_auth.RESOURCE_URL, scopes=["daylight:read", "daylight:write"])
        db.add(grant)
        db.flush()
        db.add(OAuthCredential(token_hash=digest_token(raw), grant_id=grant.id, kind="access",
                scopes=["daylight:read"], family_id=str(uuid4()),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=10)))
        db.commit()

    monkeypatch.setattr(mcp_auth, "SessionLocal", sessionmaker(bind=db_engine))
    token = asyncio.run(mcp_auth.DaylightTokenVerifier().verify_token(raw))
    assert token is not None
    assert token.scopes == ["daylight:read"]


def test_consent_uses_this_browsers_session(client, db_engine):
    handle = secrets.token_urlsafe(32)
    binding = secrets.token_urlsafe(32)
    with Session(db_engine) as db:
        user = db.query(User).filter(User.email == "test@example.com").one()
        _create_session(db, user)  # Newer session on another device.
        db.add(OAuthAuthorizationRequest(
            handle_hash=digest_token(handle), browser_hash=digest_token(binding),
            client_id="https://claude.ai/client.json", client_name="Claude",
            redirect_uri="https://claude.ai/api/mcp/auth_callback", client_state="state",
            scopes=["daylight:read"], resource=mcp_auth.RESOURCE_URL,
            code_challenge="a" * 43, expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        ))
        db.commit()
    client.cookies.set("daylight_oauth_binding", binding)
    response = client.get(f"/oauth/continue?request={handle}")
    assert response.status_code == 200
    assert f'value="{client.headers["X-CSRF-Token"]}"' in response.text
    assert "Connect Claude to Daylight?" in response.text
    assert "Read projects and tasks" in response.text
    assert "form-action 'self' https://claude.ai;" in response.headers["content-security-policy"]


def test_mcp_server_exposes_icons_and_favicon(client):
    from app.mcp.server import mcp

    assert mcp.icons
    assert any(icon.src.endswith("/icon.png") for icon in mcp.icons)
    assert any(icon.src.endswith("/icon.svg") for icon in mcp.icons)

    assert client.get("/favicon.ico").status_code == 200
    svg = client.get("/icon.svg")
    assert svg.status_code == 200
    assert "image/svg+xml" in svg.headers["content-type"]
    png = client.get("/icon.png")
    assert png.status_code == 200
    assert "image/png" in png.headers["content-type"]


def test_google_continuation_requires_existing_browser_bound_request(client):
    response = client.get("/auth/google/start?oauth_continue=missing", follow_redirects=False)
    assert response.status_code == 400


def test_authorization_code_pkce_and_refresh_keep_granted_scopes(client, monkeypatch):
    client_id = "https://claude.ai/client.json"
    redirect_uri = "https://claude.ai/api/mcp/auth_callback"

    async def known_client(_client_id):
        assert _client_id == client_id
        return "Claude", [redirect_uri]

    monkeypatch.setattr(oauth, "_client_metadata", known_client)
    verifier = "a" * 64
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    start = client.get("/oauth/authorize", params={
        "client_id": client_id, "redirect_uri": redirect_uri, "state": "random-state",
        "resource": mcp_auth.RESOURCE_URL, "scope": "daylight:read",
        "code_challenge": challenge, "code_challenge_method": "S256",
    }, follow_redirects=False)
    assert start.status_code == 303
    handle = parse_qs(urlparse(start.headers["location"]).query)["request"][0]
    consent_url = urlparse(start.headers["location"])
    consent = client.get(f"{consent_url.path}?{consent_url.query}")
    assert consent.status_code == 200
    approval = client.post("/oauth/authorize/decision", data={
        "request": handle, "csrf": client.headers["X-CSRF-Token"], "decision": "approve",
    }, headers={"Origin": "http://localhost:8000"}, follow_redirects=False)
    assert approval.status_code == 303
    assert parse_qs(urlparse(approval.headers["location"]).query)["state"] == ["random-state"]
    code = parse_qs(urlparse(approval.headers["location"]).query)["code"][0]
    fields = {"grant_type": "authorization_code", "client_id": client_id,
              "redirect_uri": redirect_uri, "resource": mcp_auth.RESOURCE_URL, "code": code}
    invalid = client.post("/oauth/token", data={**fields, "code_verifier": "b" * 64})
    assert invalid.status_code == 400
    issued = client.post("/oauth/token", data={**fields, "code_verifier": verifier})
    assert issued.status_code == 200
    assert issued.json()["scope"] == "daylight:read"
    assert client.post("/oauth/token", data={**fields, "code_verifier": verifier}).status_code == 400
    refreshed = client.post("/oauth/token", data={"grant_type": "refresh_token",
        "client_id": client_id, "resource": mcp_auth.RESOURCE_URL,
        "refresh_token": issued.json()["refresh_token"]})
    assert refreshed.status_code == 200
    assert refreshed.json()["scope"] == "daylight:read"
