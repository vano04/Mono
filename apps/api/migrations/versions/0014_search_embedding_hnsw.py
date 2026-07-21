"""Ensure semantic search has its PostgreSQL HNSW index.

Revision ID: 0014_search_embedding_hnsw
Revises: 0013_identity_locale
"""

from alembic import op


revision = "0014_search_embedding_hnsw"
down_revision = "0013_identity_locale"
branch_labels = None
depends_on = None


INDEX_NAME = "ix_search_documents_embedding_hnsw"


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        f"CREATE INDEX IF NOT EXISTS {INDEX_NAME} ON search_documents "
        "USING hnsw (embedding vector_cosine_ops) WHERE embedding IS NOT NULL"
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
