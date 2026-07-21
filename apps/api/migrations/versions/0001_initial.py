"""Initial Mono persistence schema.

Revision ID: 0001_initial
Revises:
"""

from alembic import op

from mono_api.database import Base
from mono_api import models  # noqa: F401


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
