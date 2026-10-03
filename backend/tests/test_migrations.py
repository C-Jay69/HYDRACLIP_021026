"""Regression tests for database migrations."""

from __future__ import annotations

import importlib

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def test_initial_migration_uses_safe_postgres_types(monkeypatch):
    """Enum DDL and seed values must carry explicit PostgreSQL-safe types."""

    migration = importlib.import_module(
        "apps.api.migrations.versions.20260930_initial"
    )
    created_enums: list[tuple[str, bool]] = []
    tables: dict[str, tuple[object, ...]] = {}
    bulk_insert_tables: dict[str, object] = {}

    class FakeOperations:
        @staticmethod
        def get_bind():
            return object()

        @staticmethod
        def create_table(name, *columns, **_kwargs):
            tables[name] = columns

        @staticmethod
        def create_index(*_args, **_kwargs):
            return None

        @staticmethod
        def bulk_insert(table, _rows, **_kwargs):
            bulk_insert_tables[table.name] = table

        @staticmethod
        def f(name):
            return name

    def record_enum_create(self, _bind, checkfirst=True):
        created_enums.append((self.name, checkfirst))

    monkeypatch.setattr(migration, "op", FakeOperations())
    monkeypatch.setattr(postgresql.ENUM, "create", record_enum_create)

    migration.upgrade()

    expected_enum_names = {
        "user_role",
        "subscription_status",
        "schedule_status",
        "published_post_status",
        "video_job_status",
    }
    assert {name for name, _checkfirst in created_enums} == expected_enum_names
    assert all(checkfirst for _name, checkfirst in created_enums)

    status_tables = {
        "subscriptions": "subscription_status",
        "video_jobs": "video_job_status",
        "schedules": "schedule_status",
        "published_posts": "published_post_status",
    }
    for table_name, enum_name in status_tables.items():
        status_column = next(
            column for column in tables[table_name] if column.name == "status"
        )
        assert isinstance(status_column.type, postgresql.ENUM)
        assert status_column.type.name == enum_name
        assert status_column.type.create_type is False

    assert set(bulk_insert_tables) == {
        "plans",
        "system_settings",
        "prompt_templates",
    }
    for seed_table in bulk_insert_tables.values():
        assert all(
            not isinstance(column.type, sa.types.NullType)
            for column in seed_table.c
        )

    plans_seed_table = bulk_insert_tables["plans"]
    assert isinstance(plans_seed_table.c.features_json.type, sa.JSON)
