# Daylight MCP: execution plan

**Current implementation:** `/daylight` calls four owner-scoped actions through LangGraph. Daylight now also has an OAuth authorization server, a FastMCP `/mcp` mount, and password/Google browser login continuation. Claude website interoperability still requires a public HTTPS deployment and live check.

**First target:** Claude's website, using **Customize → Connectors → Add → Custom → Web**. Enter a name and Daylight's public HTTPS URL, for example `https://daylight-api.example.com/mcp` (illustrative). Claude detects Daylight's authorization requirements, the person signs in to Daylight and approves access, and Claude can then discover and call the four tools. No manually copied bearer token or separate MCP chat session. The exact Claude setup, authorization endpoints, and tests are in [the OAuth README](../oauth/README.md). See [Claude's custom connector instructions](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp).

## Part 1 — The shared action boundary

The in-app chat passes the browser-authenticated `owner_id` to `backend/app/assistant/actions.py`. An MCP host will use a Daylight OAuth access token to establish that same ID on every HTTP request. Its model chooses tools; Daylight's MCP wrapper checks the token and then invokes the shared action. MCP calls do not invoke `run_agent`, use a Groq/Gemini key, or create an in-app `AssistantConversation`.

| MCP tool | Model-visible input | Shared action |
| --- | --- | --- |
| `list_projects` | none | `list_projects_action` |
| `list_project_tasks` | `project_name` | `list_project_tasks_action` |
| `create_task` | `project_name`, `title`, optional `notes` and `priority` | `create_task_action` |
| `move_task` | `project_name`, `task_title`, `stage_name`, optional `current_stage` | `move_task_action` |

The actions use `owner_id` to select the user's projects and call existing project/task services. Exact duplicate project names and task titles can return `ok: false` with matches; the host must ask for clarification. `list_project_tasks` currently returns at most 60 tasks and a `truncated` flag. Keep these behaviors explicit in tool descriptions.

## Part 2 — MCP work with Claude's website as the first client

1. Implement the Daylight OAuth authorization flow in the linked plan, including a tested Claude client identity, consent, login continuation, token lifecycle, and public discovery. Google sign-in is already a browser login option; it does not give Claude a Daylight access token by itself.
2. Add and lock standalone FastMCP v4 (`fastmcp>=4,<5`). In `backend/app/mcp/server.py`, create `FastMCP("Daylight", auth=...)`, register the four `@mcp.tool` wrappers, and read each caller's verified access token from FastMCP's auth context. Resolve the stored Daylight `user_id`, open a short-lived database session, and return the matching shared action's result. Each listing wrapper requires `daylight:read`; each writing wrapper requires `daylight:write`. Keep `owner_id` out of every model-visible schema.
3. In `backend/app/mcp/auth.py`, configure FastMCP remote OAuth and a database-backed token verifier using hashed Daylight access-token records; reject expired, revoked, wrong-resource, or missing-user tokens. In `backend/app/main.py`, build `mcp.http_app(path="/mcp")`, mount it at `/` **after all FastAPI routes**, and combine its lifespan with FastAPI's. This makes both `/mcp` and the root well-known discovery path reachable without a trailing-slash redirect. Do not accept Daylight browser cookies or Google ID/access tokens at this endpoint.
4. Enforce the Daylight token's user, expiry, resource, and read/write scope on every tool request. Ensure an invalid or revoked token fails before a tool can execute. Keep safe domain errors readable without exposing traces or secrets.
5. Use a public HTTPS deployment or temporary HTTPS tunnel reachable from Claude's cloud. Add the URL in Claude's website, complete its sign-in and approval flow, enable the connector in a conversation, and test discovery and all four tools. Verify resulting changes via Daylight's ordinary API/UI and isolation with two users. `localhost:8000` alone cannot serve Claude's website.

**Call path:** Claude sends a bearer token to `/mcp`; the SDK verifier finds the valid Daylight access-token row and identifies its user; the wrapper checks the tool's scope; the wrapper invokes the corresponding `*_action(db, owner_id, ...)`; the action uses existing project/task services. There is no persistent Daylight MCP conversation or separate user session. Transport session IDs, if the SDK uses them, do not replace OAuth authorization.

**Implementation order:** (1) OAuth tables and migration; (2) authorization/discovery routes and Claude client metadata validation; (3) safe browser login continuation and consent; (4) code, refresh, revocation and connected-app endpoints; (5) protected SDK `/mcp` mount and four wrappers; (6) protocol and two-user checks; (7) Claude website test over public HTTPS. Complete these in one implementation pass; the README's [OAuth section](../oauth/README.md#fixed-implementation-decisions-do-not-leave-these-for-a-later-planning-pass) supplies each endpoint's inputs and outputs.

## Part 3 — Completion

The integration is complete when Claude's website can connect with Daylight's URL and interactive authorization, discover exactly these four tools, use them only on the approving user's data, refresh access, and lose access when the user disconnects it. The in-app `/daylight` chat must continue using the same actions. See [the OAuth README](../oauth/README.md) for the required endpoint contract and full acceptance cases.
