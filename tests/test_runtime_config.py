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


def test_validate_runtime_config_rejects_sqlite_database_in_production():
    with pytest.raises(RuntimeConfigError) as exc_info:
        validate_runtime_config(
            {
                "APP_ENV": "production",
                "DATABASE_URL": "sqlite:///work_schedule_ai.sqlite3",
                "REDIS_URL": "redis://localhost:6379/0",
                "WORKSCHEDULEAI_AUTH_REQUIRED": "1",
                "WORKSCHEDULEAI_SIGNED_ACTOR_SECRET": "x" * 32,
            },
            service="worker",
        )

    assert "DATABASE_URL must use PostgreSQL" in str(exc_info.value)


def test_validate_runtime_config_allows_development_defaults():
    validate_runtime_config({}, service="api")
