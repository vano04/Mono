"""Add pgvector-backed semantic search documents.

Revision ID: 0003_vector_search
Revises: 0002_project_progress_metric
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector


revision = "0003_vector_search"
down_revision = "0002_project_progress_metric"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    if "search_documents" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "search_documents",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("project_id", sa.String(length=64), nullable=False),
            sa.Column("document_type", sa.String(length=32), nullable=False),
            sa.Column("source_id", sa.String(length=64), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("embedding", Vector(384), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("document_type", "source_id"),
        )
        op.create_index("ix_search_documents_project_id", "search_documents", ["project_id"])
        op.create_index("ix_search_document_project_type", "search_documents", ["project_id", "document_type"])
        if bind.dialect.name == "postgresql":
            op.execute(
                "CREATE INDEX ix_search_documents_embedding_hnsw ON search_documents "
                "USING hnsw (embedding vector_cosine_ops) WHERE embedding IS NOT NULL"
            )


def downgrade() -> None:
    op.drop_table("search_documents")
