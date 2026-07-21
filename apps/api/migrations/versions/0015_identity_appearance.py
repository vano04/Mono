"""Add per-identity appearance preferences.

Revision ID: 0015_identity_appearance
Revises: 0014_search_embedding_hnsw
"""

import sqlalchemy as sa
from alembic import op


revision = "0015_identity_appearance"
down_revision = "0014_search_embedding_hnsw"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("identities")}
    if "theme" not in columns:
        op.add_column("identities", sa.Column("theme", sa.String(length=16), nullable=False, server_default="system"))
    if "accent_color" not in columns:
        op.add_column("identities", sa.Column("accent_color", sa.String(length=7), nullable=False, server_default="#4f46e5"))
    if "compact_rows" not in columns:
        op.add_column("identities", sa.Column("compact_rows", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("identities", "compact_rows")
    op.drop_column("identities", "accent_color")
    op.drop_column("identities", "theme")
