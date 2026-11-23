from sqlalchemy.orm import Session

from app.assistant.actions import (
    create_task_action,
    list_project_tasks_action,
    list_projects_action,
    move_task_action,
)
from app.models import User
from app.schemas.project import ProjectCreate
from app.services import project_service


def _create_user(db: Session, email: str, name: str = "User") -> User:
    user = User(name=name, email=email, password_hash="not-a-real-hash")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_move_task_action_returns_updated_stage_with_expire_on_commit_false(db_engine):
    with Session(db_engine, expire_on_commit=False) as db:
        owner = _create_user(db, "owner@example.com")
        project = project_service.create_project(db, ProjectCreate(name="Daylight"), owner.id)

        created = create_task_action(db, owner.id, "Daylight", "Authentication", priority="high")
        assert created["ok"] is True
        assert created["stage"] == "To Do"
        assert created["completed"] is False

        moved_progress = move_task_action(db, owner.id, "Daylight", "Authentication", "In Progress")
        assert moved_progress["ok"] is True
        assert moved_progress["stage"] == "In Progress"
        assert moved_progress["completed"] is False

        # Reading tasks populates task.stage in the session before moving again.
        listed = list_project_tasks_action(db, owner.id, "Daylight")
        assert listed["ok"] is True
        assert listed["tasks"][0]["stage"] == "In Progress"

        moved_completed = move_task_action(
            db,
            owner.id,
            "Daylight",
            "Authentication",
            "Completed",
            current_stage="In Progress",
        )
        assert moved_completed["ok"] is True
        assert moved_completed["stage"] == "Completed"
        assert moved_completed["completed"] is True
        assert moved_completed["project"] == project.name


def test_actions_are_owner_scoped(db_engine):
    with Session(db_engine, expire_on_commit=False) as db:
        alice = _create_user(db, "alice@example.com", "Alice")
        bob = _create_user(db, "bob@example.com", "Bob")
        project_service.create_project(db, ProjectCreate(name="Secret"), alice.id)
        create_task_action(db, alice.id, "Secret", "Private task")

        assert list_projects_action(db, bob.id) == []
        assert list_project_tasks_action(db, bob.id, "Secret")["ok"] is False
        assert move_task_action(db, bob.id, "Secret", "Private task", "Completed")["ok"] is False
