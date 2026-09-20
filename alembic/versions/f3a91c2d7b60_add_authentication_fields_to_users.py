"""add authentication fields to users

Revision ID: f3a91c2d7b60
Revises: ee65d39442b4

La revisión previa crea devices/loans, pero users proviene de create_all.
Esta revisión admite esa base y una base nueva sin reescribir el historial.
"""
from secrets import token_urlsafe

from alembic import op
import sqlalchemy as sa
from passlib.hash import bcrypt_sha256

revision = "f3a91c2d7b60"
down_revision = "ee65d39442b4"
branch_labels = None
depends_on = None


def _sequence(bind):
    return bind.execute(sa.text("SELECT seq FROM sqlite_sequence WHERE name='users'")).scalar() or 0


def _restore_sequence(bind, value):
    # El batch no debe reutilizar IDs de filas eliminadas antes de migrar.
    bind.execute(sa.text("UPDATE sqlite_sequence SET seq = max(seq, :seq) WHERE name='users'"), {"seq": value})
    if not bind.execute(sa.text("SELECT 1 FROM sqlite_sequence WHERE name='users'")).scalar():
        bind.execute(sa.text("INSERT INTO sqlite_sequence(name, seq) VALUES ('users', :seq)"), {"seq": value})


def upgrade():
    bind = op.get_bind()
    if "users" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("email", sa.String(collation="NOCASE"), nullable=False),
            sa.Column("role", sa.String(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column("hashed_password", sa.String(), nullable=False),
            sa.CheckConstraint("length(trim(name)) >= 3", name="ck_users_name"),
            sa.CheckConstraint("role IN ('admin', 'support', 'user')", name="ck_users_role"),
            sa.CheckConstraint("is_active IN (0, 1)", name="ck_users_is_active"),
            sqlite_autoincrement=True,
        )
        op.create_index("ix_users_id", "users", ["id"])
        op.create_index("ix_users_email", "users", ["email"], unique=True)
        return

    sequence = _sequence(bind)
    columns = {c["name"] for c in sa.inspect(bind).get_columns("users")}
    if "hashed_password" not in columns:
        op.add_column("users", sa.Column("hashed_password", sa.String(), nullable=True))
    users = sa.table("users", sa.column("id", sa.Integer()), sa.column("hashed_password", sa.String()))
    for user_id in bind.execute(sa.select(users.c.id).where(users.c.hashed_password.is_(None))).scalars().all():
        # Un secreto distinto por cuenta; nunca se guarda ni se imprime.
        hashed = bcrypt_sha256.hash(token_urlsafe(48))
        bind.execute(users.update().where(users.c.id == user_id).values(hashed_password=hashed))
    checks = sa.inspect(bind).get_check_constraints("users")
    table_args = () if any(c["name"] == "ck_users_is_active" for c in checks) else (
        sa.CheckConstraint("is_active IN (0, 1)", name="ck_users_is_active"),
    )
    with op.batch_alter_table("users", table_kwargs={"sqlite_autoincrement": True}, table_args=table_args) as batch:
        batch.alter_column("hashed_password", existing_type=sa.String(), nullable=False)
    _restore_sequence(bind, sequence)


def downgrade():
    bind = op.get_bind()
    sequence = _sequence(bind)
    with op.batch_alter_table("users", table_kwargs={"sqlite_autoincrement": True}) as batch:
        batch.drop_column("hashed_password")
    _restore_sequence(bind, sequence)
