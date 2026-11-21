"""add name to users

Revision ID: b0f7a91c6d42
Revises: 1c2b8d5a7f41
Create Date: 2026-11-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b0f7a91c6d42"
down_revision: Union[str, Sequence[str], None] = "1c2b8d5a7f41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("name", sa.String(length=100), nullable=True))
    op.execute("UPDATE users SET name = 'Daylight User' WHERE name IS NULL")
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "name",
            existing_type=sa.String(length=100),
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("name")
