"""Verify ownership migration preserves rows and enforces cascade deletion."""

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory


@pytest.mark.parametrize("initial_action", ["RESTRICT", "CASCADE"])
def test_owner_foreign_key_migration(initial_action):
    path = Path(__file__).resolve().parents[1] / (
        "alembic/versions/f31c2a0d97e4_merge_owner_and_restore_cascade.py"
    )
    spec = importlib.util.spec_from_file_location("owner_cascade_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        connection.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        connection.exec_driver_sql(
            "CREATE TABLE meetings (id INTEGER PRIMARY KEY, user_id INTEGER, "
            "CONSTRAINT fk_meetings_user_id_users FOREIGN KEY (user_id) "
            f"REFERENCES users(id) ON DELETE {initial_action})"
        )
        connection.exec_driver_sql("INSERT INTO users VALUES (1)")
        connection.exec_driver_sql("INSERT INTO meetings VALUES (1, 1)")
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        assert connection.exec_driver_sql("SELECT count(*) FROM meetings").scalar() == 1
        foreign_key = sa.inspect(connection).get_foreign_keys("meetings")[0]
        assert foreign_key["options"]["ondelete"] == "CASCADE"
        connection.exec_driver_sql("DELETE FROM users WHERE id = 1")
        assert connection.exec_driver_sql("SELECT count(*) FROM meetings").scalar() == 0
    engine.dispose()


def test_owner_migrations_have_one_head():
    backend = Path(__file__).resolve().parents[1]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    assert ScriptDirectory.from_config(config).get_heads() == ["f31c2a0d97e4"]
