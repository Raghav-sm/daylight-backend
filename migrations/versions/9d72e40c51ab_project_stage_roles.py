"""store designated initial and final stages per project

Revision ID: 9d72e40c51ab
Revises: b0f7a91c6d42
"""

from alembic import op
import sqlalchemy as sa


revision = "9d72e40c51ab"
down_revision = "b0f7a91c6d42"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("initial_stage_id", sa.Uuid(as_uuid=False), nullable=True))
    op.add_column("projects", sa.Column("final_stage_id", sa.Uuid(as_uuid=False), nullable=True))
    connection = op.get_bind()
    projects = sa.table("projects", sa.column("id"), sa.column("initial_stage_id"), sa.column("final_stage_id"))
    stages = sa.table("project_stages", sa.column("id"), sa.column("project_id"), sa.column("name"), sa.column("position"))
    for (project_id,) in connection.execute(sa.select(projects.c.id)):
        rows = connection.execute(sa.select(stages.c.id, stages.c.name).where(stages.c.project_id == project_id).order_by(stages.c.position)).all()
        if not rows:
            continue
        initial = next((row.id for row in rows if row.name.casefold() == "to do"), rows[0].id)
        final = next((row.id for row in rows if row.name.casefold() == "completed"), rows[-1].id)
        connection.execute(projects.update().where(projects.c.id == project_id).values(initial_stage_id=initial, final_stage_id=final))


def downgrade() -> None:
    op.drop_column("projects", "final_stage_id")
    op.drop_column("projects", "initial_stage_id")
