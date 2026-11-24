# Sign in with Google for Daylight: how it works and how we will build it

**Current state:** Daylight signs people in with an email and password. `POST /auth/login` checks the password, creates an `AuthSession`, and sets an HTTP-only `daylight_session` cookie. The frontend reads the signed-in user with `GET /auth/me`. Google sign-in is **not implemented yet**. This README covers that feature alone.

**Goal:** add **Continue with Google** to the existing login and registration screens. Once Google verifies the person, they should be signed into the *same Daylight account and workspace system* used by password login. They should not need a Google password inside Daylight.

## Part 1 — The ideas in plain language

### Who are the three participants?

| Participant | Job |
| --- | --- |
| Your browser | Moves between Daylight and Google's sign-in screen; stores Daylight's session cookie |
| Daylight (Next.js + FastAPI) | Starts sign-in, checks Google's response, finds a Daylight user, and creates a Daylight session |
| Google | Signs the person into their Google account and gives Daylight evidence of their identity |

Here **OAuth 2.0** supplies a safe *authorization-code* redirect and exchange. **OpenID Connect (OIDC)** adds the **ID token** that tells Daylight who signed in. People often call the whole thing “Google OAuth login.” The ID token is the identity proof; it is not a Daylight session. Google's [OIDC guide](https://developers.google.com/identity/openid-connect/openid-connect) describes the server flow.

### What are the code and tokens?

| Value | Who creates it? | What is it for? | Where does it go? |
| --- | --- | --- | --- |
| Google client ID | Google Cloud configuration | Names Daylight to Google | In the authorization request and backend configuration |
| Google client secret | Google Cloud configuration | Authenticates Daylight's backend during code exchange | Backend environment only |
| Authorization code | Google | Short-lived, one-use receipt after sign-in | Browser redirect to Daylight's backend callback; backend exchanges it |
| Google ID token | Google | Signed statement of the Google account identity | Backend verifies it; not used as Daylight's browser cookie |
| Google access token | Google | Allows calls to authorized Google APIs | Received in the code exchange; no Google API calls are needed for this login feature |
| Daylight session token | Daylight | Keeps the browser signed into Daylight | HTTP-only cookie, with only its hash stored in `auth_sessions` |

We ask Google only for `openid email profile`. We do not need a Google refresh token to keep a Daylight browser session alive. A person logging out of Daylight removes their Daylight session; it does not sign them out of their Google account.

### Why does the browser leave Daylight and come back?

Daylight never handles the person's Google password. It sends the browser to Google's page. Google then redirects to a **callback URL registered in Google Cloud**, for example `http://localhost:8000/auth/google/callback` locally. The browser carries a short-lived authorization code in that redirect. FastAPI exchanges the code directly with Google and checks the returned ID token. The callback must exactly match the registered redirect URI. This is a *full browser navigation*, not an AJAX call through `frontend/src/lib/api-client.ts`.

### What are `state`, `nonce`, and `redirect_uri`?

They solve different problems:

- `state` is a random, one-use value Daylight creates before leaving for Google. On the callback, Daylight matches it to the transaction started by this browser. A missing, mismatched, expired, or already used state stops sign-in. It also identifies the safe Daylight page to return to.
- `nonce` is another random value sent to Google and checked against the verified ID token. It binds that identity response to this login attempt and helps prevent replay.
- `redirect_uri` is the fixed **Daylight backend callback URL** configured in Google Cloud. It is not an arbitrary destination supplied by the browser. Separately, a post-login destination such as `/dashboard` must be an allowed internal Daylight path, never an unchecked external URL.

Think of `state` as the receipt for *this browser's attempt*, `nonce` as the marker for *this ID token*, and `redirect_uri` as the address where *Google is allowed to return the browser*. A short-lived server-side login transaction and a browser-bound transaction cookie can hold the expected values; both must be validated before accepting the callback. The cookie needs attributes compatible with the top-level Google-to-Daylight redirect (for example `SameSite=Lax` on a GET callback). Do not put a client secret or ID token into `state`.

## Part 2 — A real sign-in, one step at a time

Imagine Raghav opens `http://localhost:3000/login` and clicks **Continue with Google**. URLs and IDs below are illustrative.

### Step 1 — The button starts a browser navigation

The Next.js button navigates to `http://localhost:8000/auth/google/start`. It does not collect the Google password, obtain tokens in browser JavaScript, or create the Daylight session itself. The backend generates `state` and `nonce`, stores a short-lived transaction associated with the initiating browser, and sets a transaction cookie. It chooses `/dashboard` as the safe destination after successful sign-in.

### Step 2 — FastAPI sends the browser to Google

FastAPI redirects to Google's authorization endpoint with approximately these parameters:

```text
client_id=DAYLIGHT_GOOGLE_CLIENT_ID
redirect_uri=http://localhost:8000/auth/google/callback
response_type=code
scope=openid email profile
state=RANDOM_STATE
nonce=RANDOM_NONCE
```

The configured OIDC library should construct and validate this request. Local and deployed callback URLs need separate, exact Google Cloud registrations. In production the browser and backend use HTTPS.

### Step 3 — Google signs the person in

The person chooses a Google account and sees Google's requested account-information permissions if needed. Google redirects the browser back to Daylight:

```text
GET /auth/google/callback?code=SHORT_LIVED_GOOGLE_CODE&state=RANDOM_STATE
```

Google can also return an error if the person cancels. That path should return to Daylight with a clear message and create no session.

### Step 4 — Daylight validates the callback and exchanges the code

FastAPI checks that the returned `state` matches an unexpired, unconsumed transaction bound to this browser. It then sends the `code`, client credentials, and exact redirect URI to Google's token endpoint **from the backend**. The response contains an ID token. Use a maintained OIDC library to verify Google's signature and key rotation, `iss` (issuer), `aud` (our client ID), expiry, the expected `nonce`, and the required claims. Reject a missing or unverified email for initial account creation. Never trust a name or email passed in the browser query string. Google's [backend verification guide](https://developers.google.com/identity/sign-in/web/backend-auth) explains these checks.

An illustrative verified identity is:

```json
{
  "sub": "google-stable-account-id-123",
  "email": "raghav@example.com",
  "email_verified": true,
  "name": "Raghav"
}
```

`sub` is Google's stable identifier for this account. An email address may change or already be used by a different Daylight login method, so Daylight must not identify an existing linked Google account by email alone.

### Step 5 — Daylight chooses the right local user

| Case | Daylight behavior |
| --- | --- |
| Google `sub` is already linked to a Daylight user | Sign in that user, even if Google's display name has changed |
| New Google `sub`, verified email unused in Daylight | Create a `User` and a `GoogleIdentity` link in one transaction |
| New Google `sub`, email already on a password account | Stop with “Sign in with your password, then link Google in Account.” Do not silently merge or create a second user with the same email |
| Google `sub` linked to someone else during an attempted link | Reject the link; do not transfer account ownership |

For Google-only users, `User.password_hash` should be nullable. Password login must reject an account with no password without calling `verify_password` on `None`. Password registration remains available. A separate password-setting feature would be needed if a Google-only user later wants password login.

### Step 6 — Daylight creates its normal browser session

After the Daylight user is known, the backend reuses the existing `auth_service._create_session(db, user)` and `auth.py` cookie-setting behavior. The raw session token is sent only in an HTTP-only cookie. Its SHA-256 digest, user ID, CSRF token, and expiry live in `auth_sessions`. This is the same session mechanism used after password login; a Google ID token is not sent to the frontend as an app login token.

FastAPI then redirects the browser to the allowed Daylight page (`/dashboard` for this example). On page load, `useCurrentUser()` calls `GET /auth/me` with the session cookie. The response supplies the existing `AuthResponse` (`user` and `csrfToken`); `setCsrfToken` prepares later browser writes. The workspace gate sees an authenticated user and renders the dashboard.

### Step 7 — Later requests and logout

The browser keeps sending the Daylight cookie to FastAPI. `get_current_session` hashes the cookie token, loads `AuthSession`, checks its expiry, and `get_current_user` loads the `User`. Existing project and task endpoints need no Google-specific branch. `POST /auth/logout` deletes that Daylight session and clears the cookie. The person might still be signed into Google, so clicking Google sign-in again can be quick, but Daylight still runs a fresh callback and creates a fresh session.

```mermaid
sequenceDiagram
    participant Browser
    participant API as Daylight FastAPI
    participant Google
    Browser->>API: GET /auth/google/start
    API-->>Browser: Save transaction; redirect to Google
    Browser->>Google: Choose Google account
    Google-->>API: GET /auth/google/callback?code&state
    API->>Google: Exchange code for ID token
    Google-->>API: Signed ID token
    API-->>Browser: Daylight session cookie; redirect /dashboard
    Browser->>API: GET /auth/me with cookie
    API-->>Browser: Daylight user + CSRF token
```

## Part 3 — Existing code and proposed changes

### What already exists

`backend/app/api/auth.py` exposes `POST /auth/register`, `POST /auth/login`, `GET/PATCH /auth/me`, and `POST /auth/logout`. `backend/app/services/auth_service.py` creates an `AuthSession` with `_create_session`. `backend/app/security/dependencies.py` validates its cookie. `backend/app/models/user.py` has a required `password_hash` and unique email. The frontend login/register forms use `useLogin`/`useRegister`, then route to `/dashboard`; `useCurrentUser` loads `/auth/me` and the workspace gate depends on that result.

### The new endpoints

| Proposed endpoint | Who calls it? | Job |
| --- | --- | --- |
| `GET /auth/google/start` | Browser navigation from `/login` or `/register` | Create transaction, set browser binding, redirect to Google |
| `GET /auth/google/callback` | Google redirects the browser | Check transaction, exchange code, verify ID token, resolve user, set Daylight cookie, redirect |
| `POST /auth/google/link/start` | Signed-in user from `/account` | CSRF-protected start of explicit account linking; binds transaction to existing user |
| `GET /auth/google/status` (optional) | Account UI | Say whether Google is linked, without returning Google tokens |
| `DELETE /auth/google/link` (optional) | Signed-in user from `/account` | Unlink only if another usable login method remains; CSRF protected |

The existing `GET /auth/me` and `POST /auth/logout` remain the browser session endpoints. Linking can use the same Google callback with a transaction marked `mode="link"`; it must verify the initiating user's Daylight session again before attaching the identity. The “optional” routes are only needed if the account UI displays or manages the link. Do not add an endpoint that accepts an arbitrary Google user ID as proof of sign-in.

### The new tables and code

| Place | Planned change |
| --- | --- |
| Google Cloud | OAuth client, consent configuration, exact local and production callback URIs |
| `backend/.env.example`, `app/config.py` | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, configured backend and frontend origins; no `NEXT_PUBLIC_` secret |
| `backend/app/models/user.py` and Alembic | Allow `password_hash = NULL` for Google-only users |
| `backend/app/models/google_identity.py` and Alembic | `user_id` foreign key, provider, unique stable `sub`, email at link time, created time |
| `backend/app/models/google_login_transaction.py` or a suitable short-lived server store | One-use state/nonce, browser binding, mode, expiry, safe return destination, optional linking user ID |
| `backend/app/services/google_auth_service.py` | Start, callback validation, identity resolution/linking; reuse existing session creation |
| `backend/app/api/google_auth.py` | Redirect endpoints and cookie/redirect handling; include router in `app/main.py` |
| `frontend/src/app/(auth)/login/_components/login-form.tsx` and register form | Continue with Google button with full navigation |
| `frontend/src/app/(workspace)/account/page.tsx` | Link/status controls if account linking is included |
| Backend tests | Mock Google exchange and ID-token verification; exercise sessions and identity cases |

The transaction store can be a database table or a shared short-lived store. A process-local Python dictionary is not appropriate if callbacks may hit another worker or a restarted process. Record only the data needed for this redirect and expire/consume it. Do not store raw Google access or ID tokens for this login-only feature.

### Small code shapes, before implementation

These snippets describe the responsibilities; they are **not existing Daylight code** or a substitute for a tested OIDC library.

```python
# In the future /auth/google/start handler:
transaction = create_google_login_transaction(mode="login", return_path="/dashboard")
return redirect_to_google(
    client_id=GOOGLE_CLIENT_ID,
    redirect_uri=GOOGLE_CALLBACK_URL,
    scope="openid email profile",
    state=transaction.state,
    nonce=transaction.nonce,
)
```

```python
# In the future /auth/google/callback handler:
transaction = consume_and_validate_transaction(request, state)
identity = exchange_code_and_verify_id_token(code, transaction.nonce)
user = find_linked_user_or_create_google_user(db, identity)
_, raw_session, csrf_token = auth_service._create_session(db, user)
db.commit()
response = redirect_to_allowed_path(transaction.return_path)
set_daylight_session_cookie(response, raw_session)
return response
```

The real callback must also handle Google errors, login versus explicit linking, conflicts/races, rollbacks, and the browser binding. Avoid returning `csrf_token` in a redirect URL; `/auth/me` supplies it after navigation.

## Part 4 — Implementation order and verification

1. Configure the Google Cloud client and exact callbacks; add the OIDC dependency and backend settings. Use separate local and production configuration.
2. Add the identity and transaction storage plus the nullable-password migration. Update password login safely without changing existing users' hashes.
3. Build and test start/callback with state, nonce, verified ID token, one-use transaction, and safe return path. Reuse the Daylight session code.
4. Add the Google buttons to login and register, and make the redirected frontend reload `/auth/me` and render the current user.
5. Add deliberate linking for an existing password account from `/account`; test collisions and attempts to link one Google account to two Daylight users.
6. Exercise success, cancellation, invalid state/nonce/audience/signature, expired transactions, duplicate callbacks, verified/unverified emails, and logout. Test with two users to ensure identity never crosses accounts. Then manually test one real Google account locally and in the intended HTTPS environment.

**Done when:** a new person can use Google to enter their Daylight workspace, a linked password user can use either login method for the *same* `User.id`, existing password login still works, and both methods result in the same `/auth/me` and browser-session behavior. No Google credential is exposed to frontend JavaScript or saved as a Daylight password.
