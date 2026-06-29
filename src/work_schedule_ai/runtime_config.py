from __future__ import annotations

import os
from collections.abc import Mapping


DEFAULT_SQLITE_DATABASE_URL = "sqlite:///work_schedule_ai.sqlite3"
SIGNED_SECRET_MIN_LENGTH = 32
MAX_SOLVER_TIMEOUT_SECONDS = 120


class RuntimeConfigError(RuntimeError):
    pass


def get_database_url(environ: Mapping[str, str] | None = None) -> str:
    env = _env(environ)
    database_url = env.get("DATABASE_URL")
    if database_url:
        return database_url
    if is_production_environment(env):
        raise RuntimeConfigError(
            "DATABASE_URL is required when APP_ENV or Railway environment is production."
        )
    return DEFAULT_SQLITE_DATABASE_URL


def get_redis_url(environ: Mapping[str, str] | None = None) -> str | None:
    env = _env(environ)
    redis_url = env.get("REDIS_URL")
    if redis_url:
        return redis_url
    if is_production_environment(env):
        raise RuntimeConfigError(
            "REDIS_URL is required when APP_ENV or Railway environment is production."
        )
    return None


def validate_runtime_config(
    environ: Mapping[str, str] | None = None,
    *,
    service: str,
) -> None:
    env = _env(environ)
    if not is_production_environment(env):
        return

    problems: list[str] = []
    database_url = env.get("DATABASE_URL")
    if not database_url:
        problems.append("DATABASE_URL is required.")
    elif not _is_postgresql_database_url(database_url):
        problems.append("DATABASE_URL must use PostgreSQL in production.")

    if not env.get("REDIS_URL"):
        problems.append("REDIS_URL is required.")

    if env.get("WORKSCHEDULEAI_AUTH_REQUIRED") != "1":
        problems.append("WORKSCHEDULEAI_AUTH_REQUIRED must be set to 1.")

    actor_secret = env.get("WORKSCHEDULEAI_SIGNED_ACTOR_SECRET")
    if not actor_secret:
        problems.append("WORKSCHEDULEAI_SIGNED_ACTOR_SECRET is required.")
    elif len(actor_secret) < SIGNED_SECRET_MIN_LENGTH:
        problems.append(
            "WORKSCHEDULEAI_SIGNED_ACTOR_SECRET must be at least "
            f"{SIGNED_SECRET_MIN_LENGTH} characters."
        )

    employee_link_secret = env.get("WORKSCHEDULEAI_EMPLOYEE_LINK_SECRET")
    if service == "api":
        if not employee_link_secret:
            problems.append("WORKSCHEDULEAI_EMPLOYEE_LINK_SECRET is required.")
        elif len(employee_link_secret) < SIGNED_SECRET_MIN_LENGTH:
            problems.append(
                "WORKSCHEDULEAI_EMPLOYEE_LINK_SECRET must be at least "
                f"{SIGNED_SECRET_MIN_LENGTH} characters."
            )

    queue_lease_seconds = env.get("WORKSCHEDULEAI_QUEUE_LEASE_SECONDS")
    if queue_lease_seconds:
        try:
            parsed_queue_lease_seconds = int(queue_lease_seconds)
        except ValueError:
            problems.append("WORKSCHEDULEAI_QUEUE_LEASE_SECONDS must be an integer.")
        else:
            if parsed_queue_lease_seconds <= MAX_SOLVER_TIMEOUT_SECONDS:
                problems.append(
                    "WORKSCHEDULEAI_QUEUE_LEASE_SECONDS must be greater than "
                    f"{MAX_SOLVER_TIMEOUT_SECONDS} seconds."
                )

    if problems:
        joined = " ".join(problems)
        raise RuntimeConfigError(f"Invalid {service} runtime configuration: {joined}")


def is_production_environment(environ: Mapping[str, str] | None = None) -> bool:
    env = _env(environ)
    return any(
        _is_production_value(env.get(name))
        for name in (
            "APP_ENV",
            "WORKSCHEDULEAI_ENV",
            "RAILWAY_ENVIRONMENT",
            "RAILWAY_ENVIRONMENT_NAME",
        )
    )


def _is_postgresql_database_url(database_url: str) -> bool:
    return database_url.startswith(("postgres://", "postgresql://", "postgresql+"))


def _is_production_value(value: str | None) -> bool:
    return value is not None and value.lower() in {"prod", "production"}


def _env(environ: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if environ is None else environ
