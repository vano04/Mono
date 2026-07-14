"""Replace identity display names with usernames.

Revision ID: 0008_identity_usernames
Revises: 0007_password_auth
"""

import re

import sqlalchemy as sa
from alembic import op


revision = "0008_identity_usernames"
down_revision = "0007_password_auth"
branch_labels = None
depends_on = None


def _username(value: str, used: set[str]) -> str:
    base = re.sub(r"[^a-z0-9._-]+", "-", value.strip().lower()).strip("-._") or "user"
    base = base[:32]
    if len(base) < 3:
        base = f"{base}-user"[:32]
    candidate = base
    suffix = 2
    while candidate in used:
        ending = f"-{suffix}"
        candidate = f"{base[:32 - len(ending)]}{ending}"
        suffix += 1
    used.add(candidate)
    return candidate


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("identities")}
    if "username" not in columns:
        with op.batch_alter_table("identities") as batch:
            batch.alter_column("name", new_column_name="username", existing_type=sa.String(length=200))

    identities = sa.table("identities", sa.column("id", sa.String), sa.column("username", sa.String))
    rows = op.get_bind().execute(sa.select(identities.c.id, identities.c.username).order_by(identities.c.id)).all()
    used: set[str] = set()
    normalized = [(identity_id, _username(current, used)) for identity_id, current in rows]
    for index, (identity_id, _) in enumerate(normalized):
        op.get_bind().execute(
            identities.update().where(identities.c.id == identity_id).values(username=f"migration-{index}-{identity_id[:8]}")
        )
    for identity_id, username in normalized:
        op.get_bind().execute(
            identities.update().where(identities.c.id == identity_id).values(username=username)
        )
    with op.batch_alter_table("identities") as batch:
        batch.alter_column("username", existing_type=sa.String(length=200), type_=sa.String(length=32))


def downgrade() -> None:
    with op.batch_alter_table("identities") as batch:
        batch.alter_column("username", new_column_name="name", existing_type=sa.String(length=32), type_=sa.String(length=200))
