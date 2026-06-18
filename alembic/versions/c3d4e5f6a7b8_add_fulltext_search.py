"""add full-text search GIN index on documents

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-18 14:30:00.000000

Adds a functional GIN index over to_tsvector(name + text_content) so keyword
search uses an index instead of a sequential scan.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TSVECTOR = (
    "to_tsvector('english', " "coalesce(name, '') || ' ' || coalesce(text_content, ''))"
)


def upgrade() -> None:
    op.execute(
        f"CREATE INDEX IF NOT EXISTS idx_doc_fts "
        f"ON documents USING GIN ({_TSVECTOR})"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_doc_fts")
