import pytest

from work_schedule_ai.runtime_config import RuntimeConfigError, validate_runtime_config


def test_validate_runtime_config_rejects_missing_production_dependencies():
    with pytest.raises(RuntimeConfigError) as exc_info:
        validate_runtime_config({"APP_ENV": "production"}, service="api")

    message = str(exc_info.value)
    assert "DATABASE_URL" in message
    assert "REDIS_URL" in message
    assert "WORKSCHEDULEAI_AUTH_REQUIRED" in message
    assert "WORKSCHEDULEAI_SIGNED_ACTOR_SECRET" in message
    assert "WORKSCHEDULEAI_EMPLOYEE_LINK_SECRET" in message


def test_validate_runtime_config_rejects_sqlite_database_in_production():
    with pytest.raises(RuntimeConfigError) as exc_info:
        validate_runtime_config(
            {
                "APP_ENV": "production",
                "DATABASE_URL": "sqlite:///work_schedule_ai.sqlite3",
                "REDIS_URL": "redis://localhost:6379/0",
                "WORKSCHEDULEAI_AUTH_REQUIRED": "1",
                "WORKSCHEDULEAI_SIGNED_ACTOR_SECRET": "x" * 32,
                "WORKSCHEDULEAI_EMPLOYEE_LINK_SECRET": "y" * 32,
            },
            service="worker",
        )

    assert "DATABASE_URL must use PostgreSQL" in str(exc_info.value)


def test_validate_runtime_config_allows_development_defaults():
    validate_runtime_config({}, service="api")


def test_validate_runtime_config_rejects_weak_employee_link_secret():
    with pytest.raises(RuntimeConfigError) as exc_info:
        validate_runtime_config(
            {
                "APP_ENV": "production",
                "DATABASE_URL": "postgresql://db/internal",
                "REDIS_URL": "redis://localhost:6379/0",
                "WORKSCHEDULEAI_AUTH_REQUIRED": "1",
                "WORKSCHEDULEAI_SIGNED_ACTOR_SECRET": "x" * 32,
                "WORKSCHEDULEAI_EMPLOYEE_LINK_SECRET": "short",
            },
            service="api",
        )

    assert "WORKSCHEDULEAI_EMPLOYEE_LINK_SECRET" in str(exc_info.value)


def test_validate_runtime_config_rejects_short_queue_lease_seconds():
    with pytest.raises(RuntimeConfigError) as exc_info:
        validate_runtime_config(
            {
                "APP_ENV": "production",
                "DATABASE_URL": "postgresql://db/internal",
                "REDIS_URL": "redis://localhost:6379/0",
                "WORKSCHEDULEAI_AUTH_REQUIRED": "1",
                "WORKSCHEDULEAI_SIGNED_ACTOR_SECRET": "x" * 32,
                "WORKSCHEDULEAI_EMPLOYEE_LINK_SECRET": "y" * 32,
                "WORKSCHEDULEAI_QUEUE_LEASE_SECONDS": "60",
            },
            service="worker",
        )

    assert "WORKSCHEDULEAI_QUEUE_LEASE_SECONDS" in str(exc_info.value)
    assert "120" in str(exc_info.value)
