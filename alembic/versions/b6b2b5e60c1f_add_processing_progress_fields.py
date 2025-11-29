"""add processing progress fields to documents

Revision ID: b6b2b5e60c1f
Revises: c2d2a370740b
Create Date: 2025-12-10 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b6b2b5e60c1f"
down_revision: Union[str, None] = "c2d2a370740b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("processing_step", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column(
            "processing_progress", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "documents",
        sa.Column("processing_duration_ms", sa.Integer(), nullable=True),
    )
    op.execute("UPDATE documents SET processing_progress = 0 WHERE processing_progress IS NULL")
    op.alter_column("documents", "processing_progress", server_default=None)


def downgrade() -> None:
    op.drop_column("documents", "processing_duration_ms")
    op.drop_column("documents", "processing_progress")
    op.drop_column("documents", "processing_step")
