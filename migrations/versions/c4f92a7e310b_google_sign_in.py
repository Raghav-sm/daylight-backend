"""add google sign-in identities, transactions, and nullable password_hash

Revision ID: c4f92a7e310b
Revises: a8e31f4c92bd
"""

from alembic import op
import sqlalchemy as sa


revision = "c4f92a7e310b"
down_revision = "a8e31f4c92bd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "password_hash",
        existing_type=sa.String(length=255),
        nullable=True,
    )

    op.create_table(
        "google_identities",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("email_at_link_time", sa.String(length=254), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_google_identities_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_google_identities")),
        sa.UniqueConstraint("provider", "subject", name="uq_google_identities_provider_subject"),
        sa.UniqueConstraint("user_id", "provider", name="uq_google_identities_user_provider"),
    )
    op.create_index("ix_google_identities_user_id", "google_identities", ["user_id"])

    op.create_table(
        "google_login_transactions",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("browser_binding_hash", sa.String(length=64), nullable=False),
        sa.Column("nonce", sa.String(length=128), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("return_path", sa.String(length=255), nullable=False),
        sa.Column("origin_page", sa.String(length=32), nullable=False),
        sa.Column("linking_user_id", sa.Uuid(as_uuid=False), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["linking_user_id"],
            ["users.id"],
            name=op.f("fk_google_login_transactions_linking_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_google_login_transactions")),
        sa.UniqueConstraint("state_hash", name=op.f("uq_google_login_transactions_state_hash")),
    )
    op.create_index("ix_google_login_transactions_state_hash", "google_login_transactions", ["state_hash"])


def downgrade() -> None:
    op.drop_index("ix_google_login_transactions_state_hash", table_name="google_login_transactions")
    op.drop_table("google_login_transactions")
    op.drop_index("ix_google_identities_user_id", table_name="google_identities")
    op.drop_table("google_identities")
    op.alter_column(
        "users",
        "password_hash",
        existing_type=sa.String(length=255),
        nullable=False,
    )
