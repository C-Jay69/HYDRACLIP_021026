"""Regression tests for database migrations."""

from __future__ import annotations

import importlib

from sqlalchemy.dialects import postgresql


def test_initial_migration_does_not_create_postgres_enums_twice(monkeypatch):
    """Pre-created enum types must not be re-created by CREATE TABLE events."""

    migration = importlib.import_module(
        "apps.api.migrations.versions.20260930_initial"
    )
    created_enums: list[tuple[str, bool]] = []
    tables: dict[str, tuple[object, ...]] = {}

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
        def bulk_insert(*_args, **_kwargs):
            return None

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
