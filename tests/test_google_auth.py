from datetime import datetime, timedelta, timezone
import time
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
import httpx
from joserfc import jwt
from joserfc.jwk import RSAKey
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import app as fastapi_app
from app.models import GoogleIdentity, GoogleLoginTransaction, User
from app.services import google_auth_service


def test_google_exchange_logs_safe_provider_error(monkeypatch, caplog):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "do-not-log-secret")

    def rejected_exchange(url, *, data, headers, timeout):
        assert data["code"] == "do-not-log-code"
        return httpx.Response(400, json={"error": "invalid_grant", "error_description": "do-not-log-description"})

    monkeypatch.setattr(google_auth_service.httpx, "post", rejected_exchange)
    with pytest.raises(google_auth_service.GoogleAuthError) as error:
        google_auth_service.exchange_code_for_id_token("do-not-log-code")

    assert error.value.code == "exchange_failed"
    assert "status=400 error=invalid_grant" in caplog.text
    assert "do-not-log-secret" not in caplog.text
    assert "do-not-log-code" not in caplog.text
    assert "do-not-log-description" not in caplog.text


@pytest.fixture()
def google_oidc_fixture(monkeypatch):
    rsa_key = RSAKey.generate_key(2048, parameters={"kid": "test-kid-1", "use": "sig", "alg": "RS256"})
    jwks = {"keys": [rsa_key.as_dict(private=False)]}
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-google-client-id.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-google-client-secret")
    monkeypatch.setattr(google_auth_service, "fetch_google_jwks", lambda force_refresh=False: jwks)

    def make_id_token(
        *,
        sub: str = "google-sub-123",
        email: str = "newuser@gmail.com",
        email_verified: bool = True,
        name: str = "Raghav",
        nonce: str = "nonce-value",
        aud: str = "test-google-client-id.apps.googleusercontent.com",
        iss: str = "https://accounts.google.com",
        exp_offset: int = 300,
        signing_key: RSAKey | None = None,
    ) -> str:
        key = signing_key or rsa_key
        claims = {
            "iss": iss,
            "aud": aud,
            "sub": sub,
            "email": email,
            "email_verified": email_verified,
            "name": name,
            "nonce": nonce,
            "exp": int(time.time()) + exp_offset,
        }
        return jwt.encode({"alg": "RS256", "kid": key.kid or "test-kid-1"}, claims, key)

    return make_id_token


@pytest.fixture()
def anon_client(db_engine):
    def override_get_db():
        with Session(db_engine) as session:
            yield session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(fastapi_app) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()


def _extract_google_redirect_params(response) -> dict[str, str]:
    assert response.status_code == 302
    parsed = urlparse(response.headers["location"])
    assert parsed.scheme == "https"
    assert parsed.netloc == "accounts.google.com"
    params = parse_qs(parsed.query)
    return {key: values[0] for key, values in params.items()}


def test_google_login_creates_new_user_and_sets_daylight_session(
    anon_client, db_engine, google_oidc_fixture, monkeypatch
):
    start_resp = anon_client.get("/auth/google/start?return_to=/dashboard&origin_page=login", follow_redirects=False)
    params = _extract_google_redirect_params(start_resp)
    assert params["client_id"] == "test-google-client-id.apps.googleusercontent.com"
    assert params["scope"] == "openid email profile"
    assert params["response_type"] == "code"

    id_token = google_oidc_fixture(
        sub="google-sub-new-1",
        email="raghav@gmail.com",
        name="Raghav",
        nonce=params["nonce"],
    )
    monkeypatch.setattr(google_auth_service, "exchange_code_for_id_token", lambda code: id_token)

    cb_resp = anon_client.get(
        f"/auth/google/callback?code=fake-google-code&state={params['state']}",
        follow_redirects=False,
    )
    assert cb_resp.status_code == 302
    assert cb_resp.headers["location"] == "http://localhost:3000/dashboard"

    # Normal Daylight /auth/me now works with the issued cookie.
    me_resp = anon_client.get("/auth/me")
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["user"]["email"] == "raghav@gmail.com"
    assert me_data["user"]["name"] == "Raghav"
    assert me_data["csrfToken"]

    # Google-only user has NULL password_hash and password login fails cleanly with 401.
    with Session(db_engine) as db:
        user = db.scalar(select(User).where(User.email == "raghav@gmail.com"))
        assert user is not None
        assert user.password_hash is None
        identity = db.scalar(select(GoogleIdentity).where(GoogleIdentity.user_id == user.id))
        assert identity is not None
        assert identity.subject == "google-sub-new-1"

    pw_resp = anon_client.post(
        "/auth/login",
        headers={"Origin": "http://localhost:3000"},
        json={"email": "raghav@gmail.com", "password": "some-long-password"},
    )
    assert pw_resp.status_code == 401

    # Status reports Google linked and cannot unlink without a password.
    status_resp = anon_client.get("/auth/google/status")
    assert status_resp.status_code == 200
    assert status_resp.json() == {
        "configured": True,
        "linked": True,
        "linkedEmail": "raghav@gmail.com",
        "hasPassword": False,
        "canUnlink": False,
    }

    # Replay of the same callback state is rejected.
    replay_resp = anon_client.get(
        f"/auth/google/callback?code=fake-google-code&state={params['state']}",
        follow_redirects=False,
    )
    assert replay_resp.status_code == 302
    assert "google_error=invalid_state" in replay_resp.headers["location"]


def test_google_login_does_not_silently_merge_existing_password_account(
    anon_client, google_oidc_fixture, monkeypatch
):
    reg = anon_client.post(
        "/auth/register",
        headers={"Origin": "http://localhost:3000"},
        json={"name": "Existing User", "email": "existing@gmail.com", "password": "strong-password-123"},
    )
    assert reg.status_code == 201
    # Log out so we test fresh Google login.
    anon_client.post(
        "/auth/logout",
        headers={"Origin": "http://localhost:3000", "X-CSRF-Token": reg.json()["csrfToken"]},
    )

    start_resp = anon_client.get("/auth/google/start?origin_page=login", follow_redirects=False)
    params = _extract_google_redirect_params(start_resp)
    id_token = google_oidc_fixture(
        sub="google-sub-collision",
        email="existing@gmail.com",
        nonce=params["nonce"],
    )
    monkeypatch.setattr(google_auth_service, "exchange_code_for_id_token", lambda code: id_token)

    cb_resp = anon_client.get(
        f"/auth/google/callback?code=code-1&state={params['state']}",
        follow_redirects=False,
    )
    assert cb_resp.status_code == 302
    assert cb_resp.headers["location"] == "http://localhost:3000/login?google_error=account_exists"
    assert anon_client.get("/auth/me").status_code == 401


def test_explicit_account_link_then_google_login_and_unlink(
    client, db_engine, google_oidc_fixture, monkeypatch
):
    # `client` fixture is already registered/logged in as test@example.com with a password.
    original_user_id = client.get("/auth/me").json()["user"]["id"]

    link_start = client.post("/auth/google/link/start")
    assert link_start.status_code == 200
    auth_url = link_start.json()["authorizationUrl"]
    params = {k: v[0] for k, v in parse_qs(urlparse(auth_url).query).items()}

    id_token = google_oidc_fixture(
        sub="google-sub-linked-1",
        email="test@example.com",
        nonce=params["nonce"],
    )
    monkeypatch.setattr(google_auth_service, "exchange_code_for_id_token", lambda code: id_token)

    cb_resp = client.get(
        f"/auth/google/callback?code=link-code&state={params['state']}",
        follow_redirects=False,
    )
    assert cb_resp.status_code == 302
    assert cb_resp.headers["location"] == "http://localhost:3000/account?google=linked"

    status_resp = client.get("/auth/google/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["linked"] is True
    assert status_resp.json()["canUnlink"] is True

    # Log out and sign back in with Google -> must return the exact same user ID.
    assert client.post("/auth/logout").status_code == 204
    assert client.get("/auth/me").status_code == 401

    start_resp = client.get("/auth/google/start", follow_redirects=False)
    login_params = _extract_google_redirect_params(start_resp)
    login_token = google_oidc_fixture(
        sub="google-sub-linked-1",
        email="changed-alias@gmail.com",
        name="Changed Name",
        nonce=login_params["nonce"],
    )
    monkeypatch.setattr(google_auth_service, "exchange_code_for_id_token", lambda code: login_token)

    login_cb = client.get(
        f"/auth/google/callback?code=login-code&state={login_params['state']}",
        follow_redirects=False,
    )
    assert login_cb.status_code == 302
    assert login_cb.headers["location"] == "http://localhost:3000/dashboard"

    me_after = client.get("/auth/me").json()
    assert me_after["user"]["id"] == original_user_id

    # Unlink Google (allowed because user has a password).
    client.headers["X-CSRF-Token"] = me_after["csrfToken"]
    unlink_resp = client.delete("/auth/google/link")
    assert unlink_resp.status_code == 204
    assert client.get("/auth/google/status").json()["linked"] is False


def test_google_callback_rejects_bad_nonce_wrong_aud_unverified_email_and_expired_tx(
    anon_client, db_engine, google_oidc_fixture, monkeypatch
):
    # 1. Wrong nonce
    start = anon_client.get("/auth/google/start", follow_redirects=False)
    params = _extract_google_redirect_params(start)
    bad_nonce_token = google_oidc_fixture(nonce="wrong-nonce")
    monkeypatch.setattr(google_auth_service, "exchange_code_for_id_token", lambda code: bad_nonce_token)
    resp = anon_client.get(f"/auth/google/callback?code=c&state={params['state']}", follow_redirects=False)
    assert "google_error=invalid_token" in resp.headers["location"]

    # 2. Wrong audience
    start = anon_client.get("/auth/google/start", follow_redirects=False)
    params = _extract_google_redirect_params(start)
    bad_aud_token = google_oidc_fixture(nonce=params["nonce"], aud="other-client-id")
    monkeypatch.setattr(google_auth_service, "exchange_code_for_id_token", lambda code: bad_aud_token)
    resp = anon_client.get(f"/auth/google/callback?code=c&state={params['state']}", follow_redirects=False)
    assert "google_error=invalid_token" in resp.headers["location"]

    # 3. Unverified email
    start = anon_client.get("/auth/google/start", follow_redirects=False)
    params = _extract_google_redirect_params(start)
    unverified_token = google_oidc_fixture(nonce=params["nonce"], email_verified=False)
    monkeypatch.setattr(google_auth_service, "exchange_code_for_id_token", lambda code: unverified_token)
    resp = anon_client.get(f"/auth/google/callback?code=c&state={params['state']}", follow_redirects=False)
    assert "google_error=unverified_email" in resp.headers["location"]

    # 4. Cancelled at Google
    start = anon_client.get("/auth/google/start?origin_page=register", follow_redirects=False)
    params = _extract_google_redirect_params(start)
    resp = anon_client.get(f"/auth/google/callback?error=access_denied&state={params['state']}", follow_redirects=False)
    assert resp.headers["location"] == "http://localhost:3000/register?google_error=cancelled"

    # 5. Expired transaction
    start = anon_client.get("/auth/google/start", follow_redirects=False)
    params = _extract_google_redirect_params(start)
    with Session(db_engine) as db:
        tx = db.scalars(select(GoogleLoginTransaction).order_by(GoogleLoginTransaction.created_at.desc())).first()
        assert tx is not None
        tx.expires_at = datetime.now(timezone.utc) - timedelta(seconds=5)
        db.commit()
    resp = anon_client.get(f"/auth/google/callback?code=c&state={params['state']}", follow_redirects=False)
    assert "google_error=expired" in resp.headers["location"]


def test_cannot_link_google_subject_already_owned_by_another_user(
    db_engine, google_oidc_fixture, monkeypatch
):
    def override_get_db():
        with Session(db_engine) as session:
            yield session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(fastapi_app) as alice, TestClient(fastapi_app) as bob:
            alice_reg = alice.post(
                "/auth/register",
                headers={"Origin": "http://localhost:3000"},
                json={"name": "Alice", "email": "alice@example.com", "password": "alice-password-123"},
            )
            alice.headers.update({"Origin": "http://localhost:3000", "X-CSRF-Token": alice_reg.json()["csrfToken"]})

            bob_reg = bob.post(
                "/auth/register",
                headers={"Origin": "http://localhost:3000"},
                json={"name": "Bob", "email": "bob@example.com", "password": "bob-password-1234"},
            )
            bob.headers.update({"Origin": "http://localhost:3000", "X-CSRF-Token": bob_reg.json()["csrfToken"]})

            # Alice links google-sub-shared.
            a_start = alice.post("/auth/google/link/start")
            a_params = {k: v[0] for k, v in parse_qs(urlparse(a_start.json()["authorizationUrl"]).query).items()}
            a_token = google_oidc_fixture(sub="google-sub-shared", email="alice@gmail.com", nonce=a_params["nonce"])
            monkeypatch.setattr(google_auth_service, "exchange_code_for_id_token", lambda code: a_token)
            a_cb = alice.get(f"/auth/google/callback?code=a&state={a_params['state']}", follow_redirects=False)
            assert a_cb.headers["location"] == "http://localhost:3000/account?google=linked"

            # Bob attempts to link the same Google sub -> rejected, ownership unchanged.
            b_start = bob.post("/auth/google/link/start")
            b_params = {k: v[0] for k, v in parse_qs(urlparse(b_start.json()["authorizationUrl"]).query).items()}
            b_token = google_oidc_fixture(sub="google-sub-shared", email="alice@gmail.com", nonce=b_params["nonce"])
            monkeypatch.setattr(google_auth_service, "exchange_code_for_id_token", lambda code: b_token)
            b_cb = bob.get(f"/auth/google/callback?code=b&state={b_params['state']}", follow_redirects=False)
            assert b_cb.headers["location"] == "http://localhost:3000/account?google_error=already_linked"
            assert bob.get("/auth/google/status").json()["linked"] is False
            assert alice.get("/auth/google/status").json()["linked"] is True
    finally:
        fastapi_app.dependency_overrides.clear()
