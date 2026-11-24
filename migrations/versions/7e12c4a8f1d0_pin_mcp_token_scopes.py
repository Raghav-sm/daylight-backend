"""Pin permissions to each OAuth access and refresh token.

Revision ID: 7e12c4a8f1d0
Revises: 10d5733b5c64
"""

from alembic import op
import sqlalchemy as sa

revision = "7e12c4a8f1d0"
down_revision = "10d5733b5c64"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("oauth_credentials", sa.Column("scopes", sa.JSON(), nullable=True))
    op.execute("""
        UPDATE oauth_credentials AS credential
        SET scopes = grant_row.scopes
        FROM oauth_grants AS grant_row
        WHERE credential.grant_id = grant_row.id
    """)
    op.alter_column("oauth_credentials", "scopes", nullable=False)


def downgrade() -> None:
    op.drop_column("oauth_credentials", "scopes")
