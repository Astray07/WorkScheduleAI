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
                _insert_role(connection, "role_a", "org_a", "Senior A")
                _insert_shift_type(connection, "shift_type_a", "org_a", "Day A")
                _insert_schedule_run(connection, "run_a", "org_a")
                _insert_shift_slot(connection, "slot_a", "org_a", "run_a")
                _insert_rag_document(connection, "rag_doc_a", "org_a", "Policy A")
                _set_tenant(connection, "org_b")
                _insert_employee(connection, "emp_b", "org_b", "E002")
                _insert_role(connection, "role_b", "org_b", "Senior B")
                _insert_shift_type(connection, "shift_type_b", "org_b", "Day B")
                _insert_schedule_run(connection, "run_b", "org_b")
                _insert_shift_slot(connection, "slot_b", "org_b", "run_b")
                _insert_rag_document(connection, "rag_doc_b", "org_b", "Policy B")

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

            with pytest.raises(DBAPIError):
                with app_engine.begin() as connection:
                    _set_tenant(connection, "org_a")
                    _insert_assignment(
                        connection,
                        assignment_id="assignment_cross_rls",
                        organization_id="org_b",
                        schedule_run_id="run_b",
                        shift_slot_id="slot_b",
                        role_id="role_b",
                        employee_id="emp_b",
                    )

            with pytest.raises(DBAPIError):
                with app_engine.begin() as connection:
                    _set_tenant(connection, "org_a")
                    _insert_shift_requirement(
                        connection,
                        requirement_id="requirement_cross_fk",
                        organization_id="org_a",
                        shift_type_id="shift_type_b",
                        role_id="role_a",
                    )

            with pytest.raises(DBAPIError):
                with app_engine.begin() as connection:
                    _set_tenant(connection, "org_a")
                    _insert_pair_constraint(
                        connection,
                        pair_id="pair_cross_fk",
                        organization_id="org_a",
                        employee_a_id="emp_a",
                        employee_b_id="emp_b",
                    )

            with pytest.raises(DBAPIError):
                with app_engine.begin() as connection:
                    _set_tenant(connection, "org_a")
                    _insert_compliance_warning_override(
                        connection,
                        override_id="warning_cross_fk",
                        organization_id="org_a",
                        schedule_run_id="run_b",
                    )

            with pytest.raises(DBAPIError):
                with app_engine.begin() as connection:
                    _set_tenant(connection, "org_a")
                    _insert_rag_document_chunk(
                        connection,
                        chunk_id="rag_chunk_cross_fk",
                        organization_id="org_a",
                        document_id="rag_doc_b",
                    )

            with pytest.raises(DBAPIError):
                with app_engine.begin() as connection:
                    _set_tenant(connection, "org_a")
                    _insert_assignment(
                        connection,
                        assignment_id="assignment_cross_fk",
                        organization_id="org_a",
                        schedule_run_id="run_a",
                        shift_slot_id="slot_a",
                        role_id="role_a",
                        employee_id="emp_b",
                    )
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


def _insert_role(
    connection,
    role_id: str,
    organization_id: str,
    name: str,
) -> None:
    connection.execute(
        text(
            "INSERT INTO roles (id, organization_id, name, created_at) "
            "VALUES (:id, :organization_id, :name, now())"
        ),
        {
            "id": role_id,
            "organization_id": organization_id,
            "name": name,
        },
    )


def _insert_schedule_run(
    connection,
    schedule_run_id: str,
    organization_id: str,
) -> None:
    connection.execute(
        text(
            "INSERT INTO schedule_runs "
            "(id, organization_id, period_start, period_end, template, "
            "deterministic_mode, timeout_seconds, status, solver_status, "
            "solution_quality, current_attempt_no, recalculation_count, "
            "input_snapshot_hash, idempotency_key, created_at, updated_at, "
            "started_at, finished_at, canceled_at) "
            "VALUES (:id, :organization_id, '2026-07-01', '2026-07-01', "
            "'one_shift_per_day', true, 30, 'succeeded', 'cp_sat_optimal', "
            "'optimal', 1, 0, NULL, NULL, now(), now(), NULL, NULL, NULL)"
        ),
        {
            "id": schedule_run_id,
            "organization_id": organization_id,
        },
    )


def _insert_shift_type(
    connection,
    shift_type_id: str,
    organization_id: str,
    name: str,
) -> None:
    connection.execute(
        text(
            "INSERT INTO shift_types "
            "(id, organization_id, name, local_start_time, local_end_time, "
            "timezone, crosses_midnight, active_weekdays, active, created_at) "
            "VALUES (:id, :organization_id, :name, '09:00', '17:00', "
            "'Asia/Seoul', false, '0,1,2,3,4', true, now())"
        ),
        {
            "id": shift_type_id,
            "organization_id": organization_id,
            "name": name,
        },
    )


def _insert_shift_slot(
    connection,
    shift_slot_id: str,
    organization_id: str,
    schedule_run_id: str,
) -> None:
    connection.execute(
        text(
            "INSERT INTO shift_slots "
            "(id, organization_id, schedule_run_id, shift_type_id, local_date, "
            "label, starts_at, ends_at, timezone, status, attempt_no, created_at) "
            "VALUES (:id, :organization_id, :schedule_run_id, NULL, '2026-07-01', "
            "'Day', '2026-07-01T09:00:00+09:00', "
            "'2026-07-01T17:00:00+09:00', 'Asia/Seoul', 'generated', 1, now())"
        ),
        {
            "id": shift_slot_id,
            "organization_id": organization_id,
            "schedule_run_id": schedule_run_id,
        },
    )


def _insert_shift_requirement(
    connection,
    *,
    requirement_id: str,
    organization_id: str,
    shift_type_id: str,
    role_id: str,
) -> None:
    connection.execute(
        text(
            "INSERT INTO shift_requirements "
            "(id, organization_id, shift_type_id, role_id, required_count, "
            "unfilled_weight_override, created_at) "
            "VALUES (:id, :organization_id, :shift_type_id, :role_id, 1, NULL, now())"
        ),
        {
            "id": requirement_id,
            "organization_id": organization_id,
            "shift_type_id": shift_type_id,
            "role_id": role_id,
        },
    )


def _insert_assignment(
    connection,
    *,
    assignment_id: str,
    organization_id: str,
    schedule_run_id: str,
    shift_slot_id: str,
    role_id: str,
    employee_id: str,
) -> None:
    connection.execute(
        text(
            "INSERT INTO assignments "
            "(id, organization_id, schedule_run_id, shift_slot_id, role_id, "
            "employee_id, employee_name, source, locked_by_user, warning_state, "
            "warning_message, attempt_no, created_at) "
            "VALUES (:id, :organization_id, :schedule_run_id, :shift_slot_id, "
            ":role_id, :employee_id, 'Employee', 'manual', true, 'none', "
            "NULL, 1, now())"
        ),
        {
            "id": assignment_id,
            "organization_id": organization_id,
            "schedule_run_id": schedule_run_id,
            "shift_slot_id": shift_slot_id,
            "role_id": role_id,
            "employee_id": employee_id,
        },
    )


def _insert_pair_constraint(
    connection,
    *,
    pair_id: str,
    organization_id: str,
    employee_a_id: str,
    employee_b_id: str,
) -> None:
    normalized = sorted([employee_a_id, employee_b_id])
    connection.execute(
        text(
            "INSERT INTO pair_constraints "
            "(id, organization_id, employee_a_id, employee_b_id, "
            "normalized_employee_a_id, normalized_employee_b_id, type, severity, "
            "override_allowed, active, created_at) "
            "VALUES (:id, :organization_id, :employee_a_id, :employee_b_id, "
            ":normalized_employee_a_id, :normalized_employee_b_id, "
            "'blocked', 'high', false, true, now())"
        ),
        {
            "id": pair_id,
            "organization_id": organization_id,
            "employee_a_id": employee_a_id,
            "employee_b_id": employee_b_id,
            "normalized_employee_a_id": normalized[0],
            "normalized_employee_b_id": normalized[1],
        },
    )


def _insert_compliance_warning_override(
    connection,
    *,
    override_id: str,
    organization_id: str,
    schedule_run_id: str,
) -> None:
    connection.execute(
        text(
            "INSERT INTO compliance_warning_overrides "
            "(id, organization_id, schedule_run_id, warning_code, employee_id, "
            "slot_id, week_key, snapshot_hash, reason, created_by_user_id, created_at) "
            "VALUES (:id, :organization_id, :schedule_run_id, "
            "'WEEKLY_HOURS_OVER_52', '', '', '2026-W27', 'snapshot-a', "
            "'Approved', NULL, now())"
        ),
        {
            "id": override_id,
            "organization_id": organization_id,
            "schedule_run_id": schedule_run_id,
        },
    )


def _insert_rag_document(
    connection,
    document_id: str,
    organization_id: str,
    title: str,
) -> None:
    connection.execute(
        text(
            "INSERT INTO rag_documents "
            "(id, organization_id, source_type, document_title, checked_at, "
            "content_hash, created_at) "
            "VALUES (:id, :organization_id, 'organization_policy', :title, "
            "'2026-06-27', :content_hash, now())"
        ),
        {
            "id": document_id,
            "organization_id": organization_id,
            "title": title,
            "content_hash": f"hash-{document_id}",
        },
    )


def _insert_rag_document_chunk(
    connection,
    *,
    chunk_id: str,
    organization_id: str,
    document_id: str,
) -> None:
    connection.execute(
        text(
            "INSERT INTO rag_document_chunks "
            "(id, organization_id, document_id, chunk_index, excerpt, "
            "embedding_model, embedding_dimensions, embedding_vector_json, "
            "embedding_content_hash, created_at) "
            "VALUES (:id, :organization_id, :document_id, 0, 'Evidence', "
            "NULL, NULL, NULL, NULL, now())"
        ),
        {
            "id": chunk_id,
            "organization_id": organization_id,
            "document_id": document_id,
        },
    )
