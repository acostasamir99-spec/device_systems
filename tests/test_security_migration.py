"""Migración real: bases vacías y bases EV10 con datos y secuencia histórica."""
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.auth.security import verify_password

ROOT = Path(__file__).resolve().parents[1]
HEAD = "f3a91c2d7b60"


def migrate(connection, revision, downgrade=False):
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes["connection"] = connection
    (command.downgrade if downgrade else command.upgrade)(config, revision)


@pytest.mark.parametrize("existing_users", [False, True])
def test_upgrade_preserves_data_constraints_and_history(tmp_path, existing_users):
    engine = create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    try:
        with engine.begin() as db:
            if existing_users:
                db.execute(text("""CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, name VARCHAR NOT NULL,
                    email VARCHAR COLLATE NOCASE NOT NULL, role VARCHAR NOT NULL,
                    is_active BOOLEAN DEFAULT '1' NOT NULL CHECK (is_active IN (0,1)),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    CONSTRAINT ck_users_name CHECK (length(trim(name)) >= 3),
                    CONSTRAINT ck_users_role CHECK (role IN ('admin','support','user')))
                """))
                db.execute(text("CREATE UNIQUE INDEX ix_users_email ON users (email)"))
                db.execute(text("CREATE INDEX ix_users_id ON users (id)"))
                db.execute(text("INSERT INTO users(id,name,email,role) VALUES (1,'Persona Uno','one@example.com','admin'),(2,'Persona Dos','two@example.com','support'),(99,'Eliminado','deleted@example.com','user')"))
                db.execute(text("DELETE FROM users WHERE id=99"))
            migrate(db, "ee65d39442b4")
            if existing_users:
                db.execute(text("INSERT INTO devices(id,name,serial_number,device_type) VALUES (1,'Laptop','SN-1','laptop')"))
                db.execute(text("INSERT INTO loans(id,user_id,device_id,status) VALUES (1,1,1,'active')"))
            migrate(db, "head")
            assert db.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == HEAD
            columns = {c["name"]: c for c in inspect(db).get_columns("users")}
            assert columns["hashed_password"]["nullable"] is False
            assert columns["hashed_password"]["default"] is None
            if existing_users:
                rows = db.execute(text("SELECT id,name,email,role,is_active,hashed_password FROM users ORDER BY id")).all()
                assert len(rows) == 2
                assert tuple(rows[0][:5]) == (1, "Persona Uno", "one@example.com", "admin", 1)
                assert rows[0][5] != rows[1][5]
                for row in rows:
                    assert row[5].startswith("$bcrypt-sha256$")
                    assert not verify_password("password", row[5])
                assert db.execute(text("SELECT user_id,device_id FROM loans")).one() == (1, 1)
                assert db.execute(text("SELECT seq FROM sqlite_sequence WHERE name='users'")).scalar() == 99
                assert any(i["name"] == "ix_users_email" and i["unique"] for i in inspect(db).get_indexes("users"))
            assert db.execute(text("PRAGMA integrity_check")).scalar_one() == "ok"
            assert db.execute(text("PRAGMA foreign_key_check")).all() == []
            for name, email, role, active, hashed in [
                ("Persona", "null@example.com", "user", 1, None),
                ("ab", "short@example.com", "user", 1, "not-used"),
                ("Persona", "role@example.com", "owner", 1, "not-used"),
                ("Persona", "bool@example.com", "user", 7, "not-used"),
            ]:
                with pytest.raises(IntegrityError):
                    db.execute(text("INSERT INTO users(name,email,role,is_active,hashed_password) VALUES (:name,:email,:role,:active,:hashed)"),
                               dict(name=name, email=email, role=role, active=active, hashed=hashed))
            migrate(db, "ee65d39442b4", downgrade=True)
            assert "hashed_password" not in {c["name"] for c in inspect(db).get_columns("users")}
            if existing_users:
                assert db.execute(text("SELECT count(*) FROM users")).scalar() == 2
                assert db.execute(text("SELECT seq FROM sqlite_sequence WHERE name='users'")).scalar() == 99
            migrate(db, "head")
            assert db.execute(text("PRAGMA foreign_key_check")).all() == []
    finally:
        engine.dispose()
