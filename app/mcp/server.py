from fastmcp import FastMCP
from fastmcp.server.auth import RemoteAuthProvider
from fastmcp.server.dependencies import get_access_token
from sqlalchemy.orm import Session

from app.assistant.actions import (
    create_task_action,
    list_project_tasks_action,
    list_projects_action,
    move_task_action,
)
from app.config import BACKEND_PUBLIC_URL
from app.database import SessionLocal
from app.mcp.auth import DaylightTokenVerifier


auth = RemoteAuthProvider(
    token_verifier=DaylightTokenVerifier(),
    authorization_servers=[BACKEND_PUBLIC_URL],
    base_url=BACKEND_PUBLIC_URL,
    scopes_supported=["daylight:read", "daylight:write"],
)
mcp = FastMCP("Daylight", instructions="Manage the signed-in user's Daylight projects and tasks.", auth=auth)


def _identity(required_scope: str) -> str:
    token = get_access_token()
    if token is None or required_scope not in token.scopes or not token.subject:
        raise PermissionError(f"This action requires the {required_scope} permission.")
    return token.subject


@mcp.tool
def list_projects() -> list[dict]:
    """List the signed-in user's projects, stages, and task counts."""
    owner_id = _identity("daylight:read")
    with SessionLocal() as db:
        return list_projects_action(db, owner_id)


@mcp.tool
def list_project_tasks(project_name: str) -> dict:
    """List tasks in one of the signed-in user's projects by exact project name."""
    owner_id = _identity("daylight:read")
    with SessionLocal() as db:
        return list_project_tasks_action(db, owner_id, project_name)


@mcp.tool
def create_task(project_name: str, title: str, notes: str = "", priority: str = "none") -> dict:
    """Create a task in one of the signed-in user's projects."""
    owner_id = _identity("daylight:write")
    with SessionLocal() as db:
        return create_task_action(db, owner_id, project_name, title, notes, priority)


@mcp.tool
def move_task(project_name: str, task_title: str, stage_name: str, current_stage: str | None = None) -> dict:
    """Move a task to a stage in the signed-in user's project."""
    owner_id = _identity("daylight:write")
    with SessionLocal() as db:
        return move_task_action(db, owner_id, project_name, task_title, stage_name, current_stage)
