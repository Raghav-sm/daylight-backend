"""add owner-scoped assistant conversations and messages

Revision ID: a8e31f4c92bd
Revises: 9d72e40c51ab
"""

from alembic import op
import sqlalchemy as sa


revision = "a8e31f4c92bd"
down_revision = "9d72e40c51ab"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_conversations",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("owner_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("model_id", sa.String(length=120), nullable=False),
        sa.Column("effort", sa.String(length=20), nullable=False),
        sa.Column("graph_state", sa.JSON(), nullable=True),
        sa.Column("graph_state_model_id", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_assistant_conversations_owner_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assistant_conversations")),
    )
    op.create_index("ix_assistant_conversations_owner_id", "assistant_conversations", ["owner_id"])
    op.create_index("ix_assistant_conversations_updated_at", "assistant_conversations", ["updated_at"])

    op.create_table(
        "assistant_messages",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("conversation_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Uuid(as_uuid=False), nullable=True),
        sa.Column("project_name", sa.String(length=255), nullable=True),
        sa.Column("model_id", sa.String(length=120), nullable=True),
        sa.Column("effort", sa.String(length=20), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["assistant_conversations.id"],
            name=op.f("fk_assistant_messages_conversation_id_assistant_conversations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"],
            name=op.f("fk_assistant_messages_project_id_projects"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assistant_messages")),
    )
    op.create_index("ix_assistant_messages_conversation_id", "assistant_messages", ["conversation_id"])


def downgrade() -> None:
    op.drop_index("ix_assistant_messages_conversation_id", table_name="assistant_messages")
    op.drop_table("assistant_messages")
    op.drop_index("ix_assistant_conversations_updated_at", table_name="assistant_conversations")
    op.drop_index("ix_assistant_conversations_owner_id", table_name="assistant_conversations")
    op.drop_table("assistant_conversations")
