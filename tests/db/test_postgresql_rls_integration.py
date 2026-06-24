import os
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from work_schedule_ai.api.dependencies import set_tenant_context


def test_postgresql_rls_isolates_tenant_rows():
    postgres_url = os.environ.get("TEST_POSTGRES_URL")
    if not postgres_url:
        pytest.skip("TEST_POSTGRES_URL is not configured")
    pytest.importorskip("psycopg")

    token = uuid4().hex[:12]
    database_name = f"wsa_rls_{token}"
    role_name = f"wsa_app_{token}"
    role_password = f"pass_{token}"

    admin_url = make_url(postgres_url)
    maintenance_url = admin_url.set(database=admin_url.database or "postgres")
    database_url = admin_url.set(database=database_name)
    app_url = database_url.set(username=role_name, password=role_password)

    admin_engine = create_engine(str(maintenance_url), isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{database_name}"'))

    database_engine = create_engine(str(database_url), isolation_level="AUTOCOMMIT")
    try:
        config = Config("alembic.ini")
        config.set_main_option("sqlalchemy.url", str(database_url))
        command.upgrade(config, "head")

        with database_engine.connect() as connection:
            connection.execute(
                text(f'CREATE ROLE "{role_name}" LOGIN PASSWORD \'{role_password}\''),
            )
            connection.execute(text(f'GRANT USAGE ON SCHEMA public TO "{role_name}"'))
            connection.execute(
                text(
                    f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES '
                    f'IN SCHEMA public TO "{role_name}"'
                )
            )

        app_engine = create_engine(str(app_url))
        try:
            with app_engine.begin() as connection:
                _insert_organization(connection, "org_a", "Clinic A")
                _insert_organization(connection, "org_b", "Clinic B")
                _set_tenant(connection, "org_a")
                _insert_employee(connection, "emp_a", "org_a", "E001")
                _set_tenant(connection, "org_b")
                _insert_employee(connection, "emp_b", "org_b", "E002")

            with app_engine.begin() as connection:
                _set_tenant(connection, "org_a")
                rows = connection.execute(
                    text("SELECT employee_code FROM employees ORDER BY employee_code")
                ).scalars().all()
                assert rows == ["E001"]

            with Session(app_engine) as session:
                with session.begin():
                    set_tenant_context(session, "org_b")
                    rows = session.execute(
                        text("SELECT employee_code FROM employees ORDER BY employee_code")
                    ).scalars().all()
                    assert rows == ["E002"]

            with pytest.raises(DBAPIError):
                with app_engine.begin() as connection:
                    _set_tenant(connection, "org_a")
                    _insert_employee(connection, "emp_cross", "org_b", "E999")
        finally:
            app_engine.dispose()
    finally:
        database_engine.dispose()
        with admin_engine.connect() as connection:
            connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) "
                    "FROM pg_stat_activity "
                    "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                ),
                {"database_name": database_name},
            )
            connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}"'))
            connection.execute(text(f'DROP ROLE IF EXISTS "{role_name}"'))
        admin_engine.dispose()


def _set_tenant(connection, organization_id: str) -> None:
    connection.execute(
        text("SELECT set_config('app.current_organization_id', :organization_id, true)"),
        {"organization_id": organization_id},
    )


def _insert_organization(connection, organization_id: str, name: str) -> None:
    connection.execute(
        text(
            "INSERT INTO organizations "
            "(id, name, timezone, data_version, created_at) "
            "VALUES (:id, :name, 'Asia/Seoul', 1, now())"
        ),
        {"id": organization_id, "name": name},
    )


def _insert_employee(
    connection,
    employee_id: str,
    organization_id: str,
    employee_code: str,
) -> None:
    connection.execute(
        text(
            "INSERT INTO employees "
            "(id, organization_id, employee_code, name, active, "
            "seniority_level, max_shifts_per_week, max_shifts_per_month, "
            "notes, created_at) "
            "VALUES (:id, :organization_id, :employee_code, :name, true, "
            "NULL, NULL, NULL, NULL, now())"
        ),
        {
            "id": employee_id,
            "organization_id": organization_id,
            "employee_code": employee_code,
            "name": employee_code,
        },
    )
