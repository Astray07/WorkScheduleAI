from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError


EXPECTED_TABLES = {
    "alembic_version",
    "organizations",
    "users",
    "memberships",
    "employees",
    "roles",
    "employee_roles",
    "pair_constraints",
    "unavailabilities",
    "schedule_runs",
    "schedule_input_snapshots",
    "override_approvals",
    "schedule_recalculation_requests",
    "schedule_publications",
    "shift_types",
    "shift_requirements",
    "shift_slots",
    "schedule_requirements",
    "assignments",
    "schedule_issues",
    "relaxation_proposals",
    "solver_diagnostic_events",
    "audit_logs",
    "schedule_policies",
    "employee_user_links",
    "employee_requests",
    "publication_acknowledgements",
    "publication_notifications",
    "compliance_warning_overrides",
    "rag_documents",
    "rag_document_chunks",
    "rag_query_audits",
    "demand_drivers",
    "labor_budgets",
}


def test_alembic_upgrade_head_creates_m1_foundation_tables(tmp_path):
    db_path = tmp_path / "migration-test.sqlite"

    _upgrade_head(db_path)

    engine = create_engine(f"sqlite:///{db_path}", future=True)
    inspector = inspect(engine)

    assert EXPECTED_TABLES.issubset(set(inspector.get_table_names()))


def test_alembic_upgrade_head_creates_named_constraints(tmp_path):
    db_path = tmp_path / "migration-test.sqlite"

    _upgrade_head(db_path)

    engine = create_engine(f"sqlite:///{db_path}", future=True)
    inspector = inspect(engine)

    employee_unique_names = {
        item["name"] for item in inspector.get_unique_constraints("employees")
    }
    role_unique_names = {
        item["name"] for item in inspector.get_unique_constraints("roles")
    }
    employee_role_unique_names = {
        item["name"] for item in inspector.get_unique_constraints("employee_roles")
    }
    employee_role_fk_names = {
        item["name"] for item in inspector.get_foreign_keys("employee_roles")
    }
    employee_user_link_fk_names = {
        item["name"] for item in inspector.get_foreign_keys("employee_user_links")
    }
    employee_request_fks = inspector.get_foreign_keys("employee_requests")
    employee_request_fk_names = {item["name"] for item in employee_request_fks}
    employee_request_tenant_fk = next(
        item
        for item in employee_request_fks
        if item["name"] == "fk_employee_requests_tenant_employee"
    )
    pair_unique_names = {
        item["name"] for item in inspector.get_unique_constraints("pair_constraints")
    }
    pair_fk_names = {
        item["name"] for item in inspector.get_foreign_keys("pair_constraints")
    }
    pair_check_names = {
        item["name"] for item in inspector.get_check_constraints("pair_constraints")
    }
    unavailability_check_names = {
        item["name"] for item in inspector.get_check_constraints("unavailabilities")
    }
    unavailability_fk_names = {
        item["name"] for item in inspector.get_foreign_keys("unavailabilities")
    }
    schedule_run_unique_names = {
        item["name"] for item in inspector.get_unique_constraints("schedule_runs")
    }
    schedule_run_check_names = {
        item["name"] for item in inspector.get_check_constraints("schedule_runs")
    }
    snapshot_unique_names = {
        item["name"]
        for item in inspector.get_unique_constraints("schedule_input_snapshots")
    }
    approval_unique_names = {
        item["name"] for item in inspector.get_unique_constraints("override_approvals")
    }
    approval_check_names = {
        item["name"] for item in inspector.get_check_constraints("override_approvals")
    }
    recalc_unique_names = {
        item["name"]
        for item in inspector.get_unique_constraints(
            "schedule_recalculation_requests"
        )
    }
    recalc_check_names = {
        item["name"]
        for item in inspector.get_check_constraints(
            "schedule_recalculation_requests"
        )
    }
    publication_unique_names = {
        item["name"] for item in inspector.get_unique_constraints("schedule_publications")
    }
    publication_acknowledgement_fk_names = {
        item["name"]
        for item in inspector.get_foreign_keys("publication_acknowledgements")
    }
    publication_notification_fk_names = {
        item["name"] for item in inspector.get_foreign_keys("publication_notifications")
    }
    publication_check_names = {
        item["name"] for item in inspector.get_check_constraints("schedule_publications")
    }
    shift_type_unique_names = {
        item["name"] for item in inspector.get_unique_constraints("shift_types")
    }
    shift_requirement_unique_names = {
        item["name"] for item in inspector.get_unique_constraints("shift_requirements")
    }
    shift_requirement_fk_names = {
        item["name"] for item in inspector.get_foreign_keys("shift_requirements")
    }
    shift_requirement_check_names = {
        item["name"] for item in inspector.get_check_constraints("shift_requirements")
    }
    schedule_policy_unique_names = {
        item["name"] for item in inspector.get_unique_constraints("schedule_policies")
    }
    schedule_policy_check_names = {
        item["name"] for item in inspector.get_check_constraints("schedule_policies")
    }
    compliance_override_unique_names = {
        item["name"]
        for item in inspector.get_unique_constraints("compliance_warning_overrides")
    }
    compliance_override_fk_names = {
        item["name"]
        for item in inspector.get_foreign_keys("compliance_warning_overrides")
    }
    rag_document_unique_names = {
        item["name"] for item in inspector.get_unique_constraints("rag_documents")
    }
    rag_chunk_fk_names = {
        item["name"] for item in inspector.get_foreign_keys("rag_document_chunks")
    }
    assignment_fk_names = {
        item["name"] for item in inspector.get_foreign_keys("assignments")
    }
    shift_slot_fk_names = {
        item["name"] for item in inspector.get_foreign_keys("shift_slots")
    }
    schedule_requirement_fk_names = {
        item["name"] for item in inspector.get_foreign_keys("schedule_requirements")
    }
    schedule_issue_fk_names = {
        item["name"] for item in inspector.get_foreign_keys("schedule_issues")
    }
    relaxation_proposal_fk_names = {
        item["name"] for item in inspector.get_foreign_keys("relaxation_proposals")
    }
    solver_diagnostic_fk_names = {
        item["name"] for item in inspector.get_foreign_keys(
            "solver_diagnostic_events"
        )
    }

    assert "uq_employees_organization_employee_code" in employee_unique_names
    assert "uq_employees_organization_id" in employee_unique_names
    assert "uq_roles_organization_name" in role_unique_names
    assert "uq_roles_organization_id" in role_unique_names
    assert (
        "uq_employee_roles_organization_employee_role"
        in employee_role_unique_names
    )
    assert "fk_employee_roles_tenant_employee" in employee_role_fk_names
    assert "fk_employee_roles_tenant_role" in employee_role_fk_names
    assert "fk_employee_user_links_tenant_employee" in employee_user_link_fk_names
    assert "fk_employee_requests_tenant_employee" in employee_request_fk_names
    assert employee_request_tenant_fk["constrained_columns"] == [
        "organization_id",
        "employee_id",
    ]
    assert employee_request_tenant_fk["referred_columns"] == [
        "organization_id",
        "id",
    ]
    assert "uq_pair_constraints_normalized_pair_type" in pair_unique_names
    assert "fk_pair_constraints_tenant_employee_a" in pair_fk_names
    assert "fk_pair_constraints_tenant_employee_b" in pair_fk_names
    assert "fk_pair_constraints_tenant_normalized_employee_a" in pair_fk_names
    assert "fk_pair_constraints_tenant_normalized_employee_b" in pair_fk_names
    assert "ck_pair_constraints_normalized_order" in pair_check_names
    assert "ck_unavailabilities_type" in unavailability_check_names
    assert "ck_unavailabilities_time_order" in unavailability_check_names
    assert "fk_unavailabilities_tenant_employee" in unavailability_fk_names
    assert (
        "uq_schedule_runs_organization_idempotency_key"
        in schedule_run_unique_names
    )
    assert "uq_schedule_runs_organization_id" in schedule_run_unique_names
    assert "ck_schedule_runs_status" in schedule_run_check_names
    assert "ck_schedule_runs_recalculation_count" in schedule_run_check_names
    assert "uq_schedule_input_snapshots_schedule_run_id" in snapshot_unique_names
    assert "uq_override_approvals_run_proposal" in approval_unique_names
    assert "ck_override_approvals_type" in approval_check_names
    assert "uq_schedule_recalculations_run_idempotency_key" in recalc_unique_names
    assert "ck_schedule_recalculations_count" in recalc_check_names
    assert "uq_schedule_publications_schedule_run_id" in publication_unique_names
    assert "uq_schedule_publications_organization_id" in publication_unique_names
    assert "ck_schedule_publications_status" in publication_check_names
    assert "ck_schedule_publications_period_order" in publication_check_names
    assert (
        "fk_publication_acknowledgements_tenant_publication"
        in publication_acknowledgement_fk_names
    )
    assert (
        "fk_publication_acknowledgements_tenant_employee"
        in publication_acknowledgement_fk_names
    )
    assert (
        "fk_publication_notifications_tenant_publication"
        in publication_notification_fk_names
    )
    assert (
        "fk_publication_notifications_tenant_employee"
        in publication_notification_fk_names
    )
    assert "uq_shift_types_organization_name" in shift_type_unique_names
    assert "uq_shift_types_organization_id" in shift_type_unique_names
    assert (
        "uq_shift_requirements_shift_type_role"
        in shift_requirement_unique_names
    )
    assert "fk_shift_requirements_tenant_shift_type" in shift_requirement_fk_names
    assert "fk_shift_requirements_tenant_role" in shift_requirement_fk_names
    assert "ck_shift_requirements_required_count" in shift_requirement_check_names
    assert "uq_schedule_policies_organization_id" in schedule_policy_unique_names
    assert "ck_schedule_policies_unfilled_policy" in schedule_policy_check_names
    assert (
        "uq_compliance_warning_overrides_instance"
        in compliance_override_unique_names
    )
    assert (
        "fk_compliance_warning_overrides_tenant_schedule_run"
        in compliance_override_fk_names
    )
    assert "uq_rag_documents_organization_id" in rag_document_unique_names
    assert "fk_rag_document_chunks_tenant_document" in rag_chunk_fk_names
    assert "fk_assignments_tenant_schedule_run" in assignment_fk_names
    assert "fk_assignments_tenant_shift_slot" in assignment_fk_names
    assert "fk_assignments_tenant_role" in assignment_fk_names
    assert "fk_assignments_tenant_employee" in assignment_fk_names
    assert "fk_shift_slots_tenant_schedule_run" in shift_slot_fk_names
    assert "fk_schedule_requirements_tenant_schedule_run" in schedule_requirement_fk_names
    assert "fk_schedule_requirements_tenant_shift_slot" in schedule_requirement_fk_names
    assert "fk_schedule_requirements_tenant_role" in schedule_requirement_fk_names
    assert "fk_schedule_issues_tenant_schedule_run" in schedule_issue_fk_names
    assert "fk_schedule_issues_tenant_shift_slot" in schedule_issue_fk_names
    assert "fk_schedule_issues_tenant_role" in schedule_issue_fk_names
    assert "fk_relaxation_proposals_tenant_schedule_run" in relaxation_proposal_fk_names
    assert "fk_relaxation_proposals_tenant_shift_slot" in relaxation_proposal_fk_names
    assert "fk_solver_diagnostics_tenant_schedule_run" in solver_diagnostic_fk_names
    assert "fk_solver_diagnostics_tenant_shift_slot" in solver_diagnostic_fk_names
    assert "fk_solver_diagnostics_tenant_role" in solver_diagnostic_fk_names
    assert "fk_solver_diagnostics_tenant_employee" in solver_diagnostic_fk_names


def test_alembic_upgrade_head_creates_schedule_policy_indexes(tmp_path):
    db_path = tmp_path / "migration-test.sqlite"

    _upgrade_head(db_path)

    engine = create_engine(f"sqlite:///{db_path}", future=True)
    inspector = inspect(engine)
    policy_index_names = {
        item["name"] for item in inspector.get_indexes("schedule_policies")
    }

    assert "ix_schedule_policies_organization_id" in policy_index_names


def test_alembic_upgrade_head_creates_unavailability_indexes(tmp_path):
    db_path = tmp_path / "migration-test.sqlite"

    _upgrade_head(db_path)

    engine = create_engine(f"sqlite:///{db_path}", future=True)
    inspector = inspect(engine)
    unavailability_index_names = {
        item["name"] for item in inspector.get_indexes("unavailabilities")
    }

    assert "ix_unavailabilities_organization_id" in unavailability_index_names
    assert "ix_unavailabilities_employee_id" in unavailability_index_names
    assert "ix_unavailabilities_employee_time" in unavailability_index_names


def test_alembic_upgrade_head_creates_schedule_run_indexes(tmp_path):
    db_path = tmp_path / "migration-test.sqlite"

    _upgrade_head(db_path)

    engine = create_engine(f"sqlite:///{db_path}", future=True)
    inspector = inspect(engine)
    schedule_run_index_names = {
        item["name"] for item in inspector.get_indexes("schedule_runs")
    }
    snapshot_index_names = {
        item["name"] for item in inspector.get_indexes("schedule_input_snapshots")
    }

    assert "ix_schedule_runs_organization_id" in schedule_run_index_names
    assert "ix_schedule_runs_organization_period" in schedule_run_index_names
    assert "ix_schedule_input_snapshots_organization_id" in snapshot_index_names
    assert "ix_schedule_input_snapshots_schedule_run_id" in snapshot_index_names


def test_alembic_upgrade_head_creates_override_approval_indexes(tmp_path):
    db_path = tmp_path / "migration-test.sqlite"

    _upgrade_head(db_path)

    engine = create_engine(f"sqlite:///{db_path}", future=True)
    inspector = inspect(engine)
    approval_index_names = {
        item["name"] for item in inspector.get_indexes("override_approvals")
    }

    assert "ix_override_approvals_organization_id" in approval_index_names
    assert "ix_override_approvals_schedule_run_id" in approval_index_names


def test_alembic_upgrade_head_creates_schedule_recalculation_indexes(tmp_path):
    db_path = tmp_path / "migration-test.sqlite"

    _upgrade_head(db_path)

    engine = create_engine(f"sqlite:///{db_path}", future=True)
    inspector = inspect(engine)
    recalc_index_names = {
        item["name"]
        for item in inspector.get_indexes("schedule_recalculation_requests")
    }

    assert "ix_schedule_recalculations_organization_id" in recalc_index_names
    assert "ix_schedule_recalculations_schedule_run_id" in recalc_index_names


def test_alembic_upgrade_head_creates_schedule_publication_indexes(tmp_path):
    db_path = tmp_path / "migration-test.sqlite"

    _upgrade_head(db_path)

    engine = create_engine(f"sqlite:///{db_path}", future=True)
    inspector = inspect(engine)
    publication_index_names = {
        item["name"] for item in inspector.get_indexes("schedule_publications")
    }

    assert "ix_schedule_publications_organization_id" in publication_index_names
    assert "ix_schedule_publications_schedule_run_id" in publication_index_names
    assert "ix_schedule_publications_organization_period" in publication_index_names


def test_alembic_upgrade_head_creates_shift_template_indexes(tmp_path):
    db_path = tmp_path / "migration-test.sqlite"

    _upgrade_head(db_path)

    engine = create_engine(f"sqlite:///{db_path}", future=True)
    inspector = inspect(engine)
    shift_type_index_names = {
        item["name"] for item in inspector.get_indexes("shift_types")
    }
    shift_requirement_index_names = {
        item["name"] for item in inspector.get_indexes("shift_requirements")
    }

    assert "ix_shift_types_organization_id" in shift_type_index_names
    assert "ix_shift_requirements_organization_id" in shift_requirement_index_names
    assert "ix_shift_requirements_shift_type_id" in shift_requirement_index_names
    assert "ix_shift_requirements_role_id" in shift_requirement_index_names


def test_alembic_upgrade_head_creates_schedule_result_artifact_indexes(tmp_path):
    db_path = tmp_path / "migration-test.sqlite"

    _upgrade_head(db_path)

    engine = create_engine(f"sqlite:///{db_path}", future=True)
    inspector = inspect(engine)
    shift_slot_index_names = {
        item["name"] for item in inspector.get_indexes("shift_slots")
    }
    shift_slot_unique_names = {
        item["name"] for item in inspector.get_unique_constraints("shift_slots")
    }
    schedule_requirement_index_names = {
        item["name"] for item in inspector.get_indexes("schedule_requirements")
    }
    assignment_index_names = {
        item["name"] for item in inspector.get_indexes("assignments")
    }
    assignment_unique_names = {
        item["name"] for item in inspector.get_unique_constraints("assignments")
    }
    issue_index_names = {
        item["name"] for item in inspector.get_indexes("schedule_issues")
    }
    proposal_index_names = {
        item["name"] for item in inspector.get_indexes("relaxation_proposals")
    }
    diagnostic_index_names = {
        item["name"] for item in inspector.get_indexes("solver_diagnostic_events")
    }

    assert "ix_shift_slots_organization_id" in shift_slot_index_names
    assert "ix_shift_slots_schedule_run_id" in shift_slot_index_names
    assert "uq_shift_slots_organization_id" in shift_slot_unique_names
    assert "ix_schedule_requirements_schedule_run_id" in schedule_requirement_index_names
    assert "ix_schedule_requirements_shift_slot_id" in schedule_requirement_index_names
    assert "ix_assignments_schedule_run_id" in assignment_index_names
    assert "ix_assignments_shift_slot_id" in assignment_index_names
    assert "ix_assignments_employee_id" in assignment_index_names
    assert "uq_assignments_run_slot_role_employee" in assignment_unique_names
    assert "uq_assignments_run_slot_employee" in assignment_unique_names
    assert "ix_schedule_issues_schedule_run_id" in issue_index_names
    assert "ix_relaxation_proposals_schedule_run_id" in proposal_index_names
    assert "ix_solver_diagnostics_organization_id" in diagnostic_index_names
    assert "ix_solver_diagnostics_schedule_run_id" in diagnostic_index_names
    assert "ix_solver_diagnostics_shift_slot_id" in diagnostic_index_names
    assert "ix_solver_diagnostics_employee_id" in diagnostic_index_names


def test_alembic_upgrade_head_creates_audit_log_indexes(tmp_path):
    db_path = tmp_path / "migration-test.sqlite"

    _upgrade_head(db_path)

    engine = create_engine(f"sqlite:///{db_path}", future=True)
    inspector = inspect(engine)
    audit_index_names = {
        item["name"] for item in inspector.get_indexes("audit_logs")
    }

    assert "ix_audit_logs_organization_id" in audit_index_names
    assert "ix_audit_logs_target" in audit_index_names


def test_alembic_upgrade_head_creates_shift_type_active_weekdays(tmp_path):
    db_path = tmp_path / "migration-test.sqlite"

    _upgrade_head(db_path)

    engine = create_engine(f"sqlite:///{db_path}", future=True)
    inspector = inspect(engine)
    shift_type_columns = {
        item["name"] for item in inspector.get_columns("shift_types")
    }

    assert "active_weekdays" in shift_type_columns


def test_alembic_upgrade_head_stamps_expected_revision(tmp_path):
    db_path = tmp_path / "migration-test.sqlite"

    _upgrade_head(db_path)

    engine = create_engine(f"sqlite:///{db_path}", future=True)
    with engine.connect() as connection:
        version = connection.execute(
            text("select version_num from alembic_version")
        ).scalar_one()

    assert version == "20260627_0027"


def test_alembic_upgrade_head_rejects_cross_tenant_assignment_employee(tmp_path):
    db_path = tmp_path / "migration-test.sqlite"

    _upgrade_head(db_path)

    engine = create_engine(f"sqlite:///{db_path}", future=True)
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        _insert_assignment_fk_seed_rows(connection)

        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO assignments "
                    "(id, organization_id, schedule_run_id, shift_slot_id, role_id, "
                    "employee_id, employee_name, source, locked_by_user, "
                    "warning_state, warning_message, attempt_no, created_at) "
                    "VALUES ('assignment_cross_employee', 'org_a', 'run_a', "
                    "'slot_a', 'role_a', 'emp_b', 'Cross Tenant', 'manual', 1, "
                    "'none', NULL, 1, CURRENT_TIMESTAMP)"
                )
            )


def test_alembic_upgrade_head_rejects_existing_cross_tenant_employee_children(tmp_path):
    db_path = tmp_path / "migration-test.sqlite"

    _upgrade_head(db_path)

    engine = create_engine(f"sqlite:///{db_path}", future=True)
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        _insert_employee_child_fk_seed_rows(connection)

    _assert_integrity_error(
        engine,
        "INSERT INTO employee_roles "
        "(id, organization_id, employee_id, role_id, priority, active, created_at) "
        "VALUES ('employee_role_cross_employee', 'org_a', 'emp_b', 'role_a', "
        "100, 1, CURRENT_TIMESTAMP)",
    )
    _assert_integrity_error(
        engine,
        "INSERT INTO employee_roles "
        "(id, organization_id, employee_id, role_id, priority, active, created_at) "
        "VALUES ('employee_role_cross_role', 'org_a', 'emp_a', 'role_b', "
        "100, 1, CURRENT_TIMESTAMP)",
    )
    _assert_integrity_error(
        engine,
        "INSERT INTO unavailabilities "
        "(id, organization_id, employee_id, type, starts_at, ends_at, "
        "override_allowed, note, created_at) "
        "VALUES ('unavailability_cross_employee', 'org_a', 'emp_b', "
        "'personal', '2026-07-01T00:00:00+09:00', "
        "'2026-07-02T00:00:00+09:00', 0, NULL, CURRENT_TIMESTAMP)",
    )
    _assert_integrity_error(
        engine,
        "INSERT INTO employee_user_links "
        "(id, organization_id, employee_id, user_id, status, created_at) "
        "VALUES ('employee_user_link_cross_employee', 'org_a', 'emp_b', "
        "'user_a', 'linked', CURRENT_TIMESTAMP)",
    )
    _assert_integrity_error(
        engine,
        "INSERT INTO employee_requests "
        "(id, organization_id, employee_id, requested_by_user_id, type, status, "
        "starts_at, ends_at, note, manager_reason, reviewed_by_user_id, "
        "reviewed_at, source_unavailability_id, created_at) "
        "VALUES ('employee_request_cross_employee', 'org_a', 'emp_b', "
        "'user_a', 'unavailable', 'pending', "
        "'2026-07-01T00:00:00+09:00', "
        "'2026-07-02T00:00:00+09:00', NULL, NULL, NULL, NULL, NULL, "
        "CURRENT_TIMESTAMP)",
    )


def test_alembic_upgrade_head_rejects_cross_tenant_publication_children(tmp_path):
    db_path = tmp_path / "migration-test.sqlite"

    _upgrade_head(db_path)

    engine = create_engine(f"sqlite:///{db_path}", future=True)
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        _insert_publication_child_fk_seed_rows(connection)

    _assert_integrity_error(
        engine,
        "INSERT INTO publication_acknowledgements "
        "(id, organization_id, publication_id, employee_id, status, "
        "acknowledged_at, created_at) "
        "VALUES ('ack_cross_employee', 'org_a', 'publication_a', 'emp_b', "
        "'pending', NULL, CURRENT_TIMESTAMP)",
    )
    _assert_integrity_error(
        engine,
        "INSERT INTO publication_acknowledgements "
        "(id, organization_id, publication_id, employee_id, status, "
        "acknowledged_at, created_at) "
        "VALUES ('ack_cross_publication', 'org_a', 'publication_b', 'emp_a', "
        "'pending', NULL, CURRENT_TIMESTAMP)",
    )
    _assert_integrity_error(
        engine,
        "INSERT INTO publication_notifications "
        "(id, organization_id, publication_id, employee_id, notification_type, "
        "channel, status, created_at, delivered_at, delivery_attempts, "
        "last_delivery_error) "
        "VALUES ('notification_cross_employee', 'org_a', 'publication_a', "
        "'emp_b', 'published', 'in_app', 'pending_recorded', CURRENT_TIMESTAMP, "
        "NULL, 0, NULL)",
    )
    _assert_integrity_error(
        engine,
        "INSERT INTO publication_notifications "
        "(id, organization_id, publication_id, employee_id, notification_type, "
        "channel, status, created_at, delivered_at, delivery_attempts, "
        "last_delivery_error) "
        "VALUES ('notification_cross_publication', 'org_a', 'publication_b', "
        "'emp_a', 'published', 'in_app', 'pending_recorded', CURRENT_TIMESTAMP, "
        "NULL, 0, NULL)",
    )


def test_alembic_upgrade_head_rejects_cross_tenant_schedule_result_children(tmp_path):
    db_path = tmp_path / "migration-test.sqlite"

    _upgrade_head(db_path)

    engine = create_engine(f"sqlite:///{db_path}", future=True)
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        _insert_schedule_result_child_fk_seed_rows(connection)

    _assert_integrity_error(
        engine,
        "INSERT INTO shift_slots "
        "(id, organization_id, schedule_run_id, shift_type_id, local_date, "
        "label, starts_at, ends_at, timezone, status, attempt_no, created_at) "
        "VALUES ('slot_cross_run', 'org_a', 'run_b', NULL, '2026-07-01', "
        "'Day', '2026-07-01T09:00:00+09:00', "
        "'2026-07-01T17:00:00+09:00', 'Asia/Seoul', 'generated', 1, "
        "CURRENT_TIMESTAMP)",
    )
    _assert_integrity_error(
        engine,
        "INSERT INTO schedule_requirements "
        "(id, organization_id, schedule_run_id, shift_slot_id, role_id, "
        "role_name, required_count, attempt_no, created_at) "
        "VALUES ('requirement_cross_run', 'org_a', 'run_b', 'slot_a', "
        "'role_a', 'Senior', 1, 1, CURRENT_TIMESTAMP)",
    )
    _assert_integrity_error(
        engine,
        "INSERT INTO schedule_requirements "
        "(id, organization_id, schedule_run_id, shift_slot_id, role_id, "
        "role_name, required_count, attempt_no, created_at) "
        "VALUES ('requirement_cross_slot', 'org_a', 'run_a', 'slot_b', "
        "'role_a', 'Senior', 1, 1, CURRENT_TIMESTAMP)",
    )
    _assert_integrity_error(
        engine,
        "INSERT INTO schedule_requirements "
        "(id, organization_id, schedule_run_id, shift_slot_id, role_id, "
        "role_name, required_count, attempt_no, created_at) "
        "VALUES ('requirement_cross_role', 'org_a', 'run_a', 'slot_a', "
        "'role_b', 'Senior', 1, 1, CURRENT_TIMESTAMP)",
    )
    _assert_integrity_error(
        engine,
        "INSERT INTO schedule_issues "
        "(id, organization_id, schedule_run_id, shift_slot_id, role_id, "
        "type, missing_count, severity, reason_code, display_message, "
        "related_proposal_ids_json, attempt_no, created_at) "
        "VALUES ('issue_cross_run', 'org_a', 'run_b', 'slot_a', 'role_a', "
        "'unfilled_requirement', 1, 'high', 'NO_AVAILABLE_CANDIDATE', "
        "'Missing', '[]', 1, CURRENT_TIMESTAMP)",
    )
    _assert_integrity_error(
        engine,
        "INSERT INTO schedule_issues "
        "(id, organization_id, schedule_run_id, shift_slot_id, role_id, "
        "type, missing_count, severity, reason_code, display_message, "
        "related_proposal_ids_json, attempt_no, created_at) "
        "VALUES ('issue_cross_slot', 'org_a', 'run_a', 'slot_b', 'role_a', "
        "'unfilled_requirement', 1, 'high', 'NO_AVAILABLE_CANDIDATE', "
        "'Missing', '[]', 1, CURRENT_TIMESTAMP)",
    )
    _assert_integrity_error(
        engine,
        "INSERT INTO schedule_issues "
        "(id, organization_id, schedule_run_id, shift_slot_id, role_id, "
        "type, missing_count, severity, reason_code, display_message, "
        "related_proposal_ids_json, attempt_no, created_at) "
        "VALUES ('issue_cross_role', 'org_a', 'run_a', 'slot_a', 'role_b', "
        "'unfilled_requirement', 1, 'high', 'NO_AVAILABLE_CANDIDATE', "
        "'Missing', '[]', 1, CURRENT_TIMESTAMP)",
    )
    _assert_integrity_error(
        engine,
        "INSERT INTO relaxation_proposals "
        "(id, organization_id, schedule_run_id, group_id, "
        "requires_proposal_ids_json, type, severity, affected_shift_slot_id, "
        "display_summary, impact_preview_json, status, attempt_no, created_at) "
        "VALUES ('proposal_cross_run', 'org_a', 'run_b', NULL, '[]', "
        "'mark_manual_review', 'high', 'slot_a', 'Review', '{}', "
        "'suggested', 1, CURRENT_TIMESTAMP)",
    )
    _assert_integrity_error(
        engine,
        "INSERT INTO relaxation_proposals "
        "(id, organization_id, schedule_run_id, group_id, "
        "requires_proposal_ids_json, type, severity, affected_shift_slot_id, "
        "display_summary, impact_preview_json, status, attempt_no, created_at) "
        "VALUES ('proposal_cross_slot', 'org_a', 'run_a', NULL, '[]', "
        "'mark_manual_review', 'high', 'slot_b', 'Review', '{}', "
        "'suggested', 1, CURRENT_TIMESTAMP)",
    )
    _assert_integrity_error(
        engine,
        "INSERT INTO solver_diagnostic_events "
        "(id, organization_id, schedule_run_id, event_type, shift_slot_id, "
        "role_id, employee_id, related_employee_ids_json, constraint_type, "
        "constraint_id, metadata_json, attempt_no, created_at) "
        "VALUES ('diagnostic_cross_run', 'org_a', 'run_b', 'candidate_removed', "
        "'slot_a', 'role_a', 'emp_a', '[]', 'role', NULL, '{}', 1, "
        "CURRENT_TIMESTAMP)",
    )
    _assert_integrity_error(
        engine,
        "INSERT INTO solver_diagnostic_events "
        "(id, organization_id, schedule_run_id, event_type, shift_slot_id, "
        "role_id, employee_id, related_employee_ids_json, constraint_type, "
        "constraint_id, metadata_json, attempt_no, created_at) "
        "VALUES ('diagnostic_cross_slot', 'org_a', 'run_a', 'candidate_removed', "
        "'slot_b', 'role_a', 'emp_a', '[]', 'role', NULL, '{}', 1, "
        "CURRENT_TIMESTAMP)",
    )
    _assert_integrity_error(
        engine,
        "INSERT INTO solver_diagnostic_events "
        "(id, organization_id, schedule_run_id, event_type, shift_slot_id, "
        "role_id, employee_id, related_employee_ids_json, constraint_type, "
        "constraint_id, metadata_json, attempt_no, created_at) "
        "VALUES ('diagnostic_cross_role', 'org_a', 'run_a', 'candidate_removed', "
        "'slot_a', 'role_b', 'emp_a', '[]', 'role', NULL, '{}', 1, "
        "CURRENT_TIMESTAMP)",
    )
    _assert_integrity_error(
        engine,
        "INSERT INTO solver_diagnostic_events "
        "(id, organization_id, schedule_run_id, event_type, shift_slot_id, "
        "role_id, employee_id, related_employee_ids_json, constraint_type, "
        "constraint_id, metadata_json, attempt_no, created_at) "
        "VALUES ('diagnostic_cross_employee', 'org_a', 'run_a', "
        "'candidate_removed', 'slot_a', 'role_a', 'emp_b', '[]', "
        "'role', NULL, '{}', 1, CURRENT_TIMESTAMP)",
    )


def test_alembic_upgrade_head_rejects_cross_tenant_reference_compliance_rag_rows(
    tmp_path,
):
    db_path = tmp_path / "migration-test.sqlite"

    _upgrade_head(db_path)

    engine = create_engine(f"sqlite:///{db_path}", future=True)
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        _insert_reference_compliance_rag_fk_seed_rows(connection)

    _assert_integrity_error(
        engine,
        "INSERT INTO shift_requirements "
        "(id, organization_id, shift_type_id, role_id, required_count, "
        "unfilled_weight_override, created_at) "
        "VALUES ('shift_requirement_cross_shift_type', 'org_a', "
        "'shift_type_b', 'role_a', 1, NULL, CURRENT_TIMESTAMP)",
    )
    _assert_integrity_error(
        engine,
        "INSERT INTO shift_requirements "
        "(id, organization_id, shift_type_id, role_id, required_count, "
        "unfilled_weight_override, created_at) "
        "VALUES ('shift_requirement_cross_role', 'org_a', "
        "'shift_type_a', 'role_b', 1, NULL, CURRENT_TIMESTAMP)",
    )
    _assert_integrity_error(
        engine,
        "INSERT INTO pair_constraints "
        "(id, organization_id, employee_a_id, employee_b_id, "
        "normalized_employee_a_id, normalized_employee_b_id, type, severity, "
        "override_allowed, active, created_at) "
        "VALUES ('pair_cross_employee', 'org_a', 'emp_a', 'emp_b', "
        "'emp_a', 'emp_b', 'blocked', 'high', 0, 1, CURRENT_TIMESTAMP)",
    )
    _assert_integrity_error(
        engine,
        "INSERT INTO compliance_warning_overrides "
        "(id, organization_id, schedule_run_id, warning_code, employee_id, "
        "slot_id, week_key, snapshot_hash, reason, created_by_user_id, created_at) "
        "VALUES ('warning_override_cross_run', 'org_a', 'run_b', "
        "'WEEKLY_HOURS_LIMIT', '', '', '2026-W27', 'snapshot-a', "
        "'Approved', NULL, CURRENT_TIMESTAMP)",
    )
    _assert_integrity_error(
        engine,
        "INSERT INTO rag_document_chunks "
        "(id, organization_id, document_id, chunk_index, excerpt, "
        "embedding_model, embedding_dimensions, embedding_vector_json, "
        "embedding_content_hash, created_at) "
        "VALUES ('rag_chunk_cross_document', 'org_a', 'rag_doc_b', 0, "
        "'Evidence', NULL, NULL, NULL, NULL, CURRENT_TIMESTAMP)",
    )


def test_alembic_upgrade_head_then_downgrade_base_round_trips(tmp_path):
    db_path = tmp_path / "migration-test.sqlite"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

    command.upgrade(config, "head")
    command.downgrade(config, "base")

    engine = create_engine(f"sqlite:///{db_path}", future=True)
    inspector = inspect(engine)

    assert set(inspector.get_table_names()).issubset({"alembic_version"})


def test_alembic_upgrade_head_creates_user_password_hash_column(tmp_path):
    db_path = tmp_path / "migration-test.sqlite"

    _upgrade_head(db_path)

    engine = create_engine(f"sqlite:///{db_path}", future=True)
    inspector = inspect(engine)
    user_columns = {item["name"] for item in inspector.get_columns("users")}

    assert "password_hash" in user_columns


def test_alembic_upgrade_head_creates_notification_delivery_columns(tmp_path):
    db_path = tmp_path / "migration-test.sqlite"

    _upgrade_head(db_path)

    engine = create_engine(f"sqlite:///{db_path}", future=True)
    inspector = inspect(engine)
    notification_columns = {
        item["name"] for item in inspector.get_columns("publication_notifications")
    }

    assert "delivered_at" in notification_columns
    assert "delivery_attempts" in notification_columns
    assert "last_delivery_error" in notification_columns


def test_alembic_upgrade_head_creates_rag_embedding_columns(tmp_path):
    db_path = tmp_path / "migration-test.sqlite"

    _upgrade_head(db_path)

    engine = create_engine(f"sqlite:///{db_path}", future=True)
    inspector = inspect(engine)
    chunk_columns = {
        item["name"] for item in inspector.get_columns("rag_document_chunks")
    }

    assert "embedding_model" in chunk_columns
    assert "embedding_dimensions" in chunk_columns
    assert "embedding_vector_json" in chunk_columns
    assert "embedding_content_hash" in chunk_columns


def test_postgresql_rls_migration_defines_tenant_policies():
    migration = Path("alembic/versions/20260624_0009_m1_postgresql_rls.py")

    content = migration.read_text(encoding="utf-8")

    assert "ENABLE ROW LEVEL SECURITY" in content
    assert "FORCE ROW LEVEL SECURITY" in content
    assert "current_setting(" in content
    assert "app.current_organization_id" in content
    for table_name in (
        "employees",
        "schedule_runs",
        "assignments",
        "schedule_issues",
        "relaxation_proposals",
    ):
        assert f'"{table_name}"' in content


def test_schedule_runs_canceled_at_repair_migration_is_idempotent():
    migration = Path("alembic/versions/20260624_0012_repair_schedule_runs_canceled_at.py")

    content = migration.read_text(encoding="utf-8")

    assert 'revision: str = "20260624_0012"' in content
    assert 'down_revision: str | None = "20260624_0011"' in content
    assert 'table_name = "schedule_runs"' in content
    assert '"canceled_at"' in content
    assert "op.add_column" in content
    assert "if _has_column" in content


def test_shift_type_active_weekdays_migration_adds_default_column():
    migration = Path("alembic/versions/20260625_0013_shift_type_active_weekdays.py")

    content = migration.read_text(encoding="utf-8")

    assert 'revision: str = "20260625_0013"' in content
    assert 'down_revision: str | None = "20260624_0012"' in content
    assert '"active_weekdays"' in content
    assert 'server_default="0,1,2,3,4,5,6"' in content


def _upgrade_head(db_path: Path) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(config, "head")


def _insert_assignment_fk_seed_rows(connection) -> None:
    connection.execute(
        text(
            "INSERT INTO organizations "
            "(id, name, timezone, data_version, created_at) "
            "VALUES "
            "('org_a', 'Clinic A', 'Asia/Seoul', 1, CURRENT_TIMESTAMP), "
            "('org_b', 'Clinic B', 'Asia/Seoul', 1, CURRENT_TIMESTAMP)"
        )
    )
    connection.execute(
        text(
            "INSERT INTO employees "
            "(id, organization_id, employee_code, name, active, seniority_level, "
            "max_shifts_per_week, max_shifts_per_month, notes, created_at) "
            "VALUES "
            "('emp_a', 'org_a', 'E001', 'Employee A', 1, NULL, NULL, NULL, NULL, CURRENT_TIMESTAMP), "
            "('emp_b', 'org_b', 'E002', 'Employee B', 1, NULL, NULL, NULL, NULL, CURRENT_TIMESTAMP)"
        )
    )
    connection.execute(
        text(
            "INSERT INTO roles (id, organization_id, name, created_at) "
            "VALUES ('role_a', 'org_a', 'Senior', CURRENT_TIMESTAMP)"
        )
    )
    connection.execute(
        text(
            "INSERT INTO schedule_runs "
            "(id, organization_id, period_start, period_end, template, "
            "deterministic_mode, timeout_seconds, status, solver_status, "
            "solution_quality, current_attempt_no, recalculation_count, "
            "input_snapshot_hash, idempotency_key, created_at, updated_at, "
            "started_at, finished_at, canceled_at) "
            "VALUES ('run_a', 'org_a', '2026-07-01', '2026-07-01', "
            "'one_shift_per_day', 1, 30, 'succeeded', 'cp_sat_optimal', "
            "'optimal', 1, 0, NULL, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, "
            "NULL, NULL, NULL)"
        )
    )
    connection.execute(
        text(
            "INSERT INTO shift_slots "
            "(id, organization_id, schedule_run_id, shift_type_id, local_date, "
            "label, starts_at, ends_at, timezone, status, attempt_no, created_at) "
            "VALUES ('slot_a', 'org_a', 'run_a', NULL, '2026-07-01', "
            "'Day', '2026-07-01T09:00:00+09:00', "
            "'2026-07-01T17:00:00+09:00', 'Asia/Seoul', 'generated', 1, "
            "CURRENT_TIMESTAMP)"
        )
    )


def _insert_employee_child_fk_seed_rows(connection) -> None:
    connection.execute(
        text(
            "INSERT INTO organizations "
            "(id, name, timezone, data_version, created_at) "
            "VALUES "
            "('org_a', 'Clinic A', 'Asia/Seoul', 1, CURRENT_TIMESTAMP), "
            "('org_b', 'Clinic B', 'Asia/Seoul', 1, CURRENT_TIMESTAMP)"
        )
    )
    connection.execute(
        text(
            "INSERT INTO employees "
            "(id, organization_id, employee_code, name, active, seniority_level, "
            "max_shifts_per_week, max_shifts_per_month, notes, created_at) "
            "VALUES "
            "('emp_a', 'org_a', 'E001', 'Employee A', 1, NULL, NULL, NULL, NULL, CURRENT_TIMESTAMP), "
            "('emp_b', 'org_b', 'E002', 'Employee B', 1, NULL, NULL, NULL, NULL, CURRENT_TIMESTAMP)"
        )
    )
    connection.execute(
        text(
            "INSERT INTO roles (id, organization_id, name, created_at) "
            "VALUES "
            "('role_a', 'org_a', 'Senior A', CURRENT_TIMESTAMP), "
            "('role_b', 'org_b', 'Senior B', CURRENT_TIMESTAMP)"
        )
    )
    connection.execute(
        text(
            "INSERT INTO users "
            "(id, email, name, password_hash, created_at) "
            "VALUES ('user_a', 'user-a@example.com', 'User A', NULL, CURRENT_TIMESTAMP)"
        )
    )


def _insert_publication_child_fk_seed_rows(connection) -> None:
    _insert_employee_child_fk_seed_rows(connection)
    connection.execute(
        text(
            "INSERT INTO schedule_runs "
            "(id, organization_id, period_start, period_end, template, "
            "deterministic_mode, timeout_seconds, status, solver_status, "
            "solution_quality, current_attempt_no, recalculation_count, "
            "input_snapshot_hash, idempotency_key, created_at, updated_at, "
            "started_at, finished_at, canceled_at) "
            "VALUES "
            "('run_a', 'org_a', '2026-07-01', '2026-07-01', "
            "'one_shift_per_day', 1, 30, 'succeeded', 'cp_sat_optimal', "
            "'optimal', 1, 0, NULL, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, "
            "NULL, NULL, NULL), "
            "('run_b', 'org_b', '2026-07-01', '2026-07-01', "
            "'one_shift_per_day', 1, 30, 'succeeded', 'cp_sat_optimal', "
            "'optimal', 1, 0, NULL, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, "
            "NULL, NULL, NULL)"
        )
    )
    connection.execute(
        text(
            "INSERT INTO schedule_publications "
            "(id, organization_id, schedule_run_id, period_start, period_end, "
            "status, assignment_snapshot_hash, issue_snapshot_hash, "
            "result_snapshot_json, published_at, created_at) "
            "VALUES "
            "('publication_a', 'org_a', 'run_a', '2026-07-01', '2026-07-01', "
            "'published', 'assignment_hash_a', 'issue_hash_a', NULL, "
            "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP), "
            "('publication_b', 'org_b', 'run_b', '2026-07-01', '2026-07-01', "
            "'published', 'assignment_hash_b', 'issue_hash_b', NULL, "
            "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
    )


def _insert_schedule_result_child_fk_seed_rows(connection) -> None:
    _insert_employee_child_fk_seed_rows(connection)
    connection.execute(
        text(
            "INSERT INTO schedule_runs "
            "(id, organization_id, period_start, period_end, template, "
            "deterministic_mode, timeout_seconds, status, solver_status, "
            "solution_quality, current_attempt_no, recalculation_count, "
            "input_snapshot_hash, idempotency_key, created_at, updated_at, "
            "started_at, finished_at, canceled_at) "
            "VALUES "
            "('run_a', 'org_a', '2026-07-01', '2026-07-01', "
            "'one_shift_per_day', 1, 30, 'succeeded', 'cp_sat_optimal', "
            "'optimal', 1, 0, NULL, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, "
            "NULL, NULL, NULL), "
            "('run_b', 'org_b', '2026-07-01', '2026-07-01', "
            "'one_shift_per_day', 1, 30, 'succeeded', 'cp_sat_optimal', "
            "'optimal', 1, 0, NULL, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, "
            "NULL, NULL, NULL)"
        )
    )
    connection.execute(
        text(
            "INSERT INTO shift_slots "
            "(id, organization_id, schedule_run_id, shift_type_id, local_date, "
            "label, starts_at, ends_at, timezone, status, attempt_no, created_at) "
            "VALUES "
            "('slot_a', 'org_a', 'run_a', NULL, '2026-07-01', "
            "'Day A', '2026-07-01T09:00:00+09:00', "
            "'2026-07-01T17:00:00+09:00', 'Asia/Seoul', 'generated', 1, "
            "CURRENT_TIMESTAMP), "
            "('slot_b', 'org_b', 'run_b', NULL, '2026-07-01', "
            "'Day B', '2026-07-01T09:00:00+09:00', "
            "'2026-07-01T17:00:00+09:00', 'Asia/Seoul', 'generated', 1, "
            "CURRENT_TIMESTAMP)"
        )
    )


def _insert_reference_compliance_rag_fk_seed_rows(connection) -> None:
    _insert_schedule_result_child_fk_seed_rows(connection)
    connection.execute(
        text(
            "INSERT INTO shift_types "
            "(id, organization_id, name, local_start_time, local_end_time, "
            "timezone, crosses_midnight, active_weekdays, active, created_at) "
            "VALUES "
            "('shift_type_a', 'org_a', 'Day A', '09:00', '17:00', "
            "'Asia/Seoul', 0, '0,1,2,3,4', 1, CURRENT_TIMESTAMP), "
            "('shift_type_b', 'org_b', 'Day B', '09:00', '17:00', "
            "'Asia/Seoul', 0, '0,1,2,3,4', 1, CURRENT_TIMESTAMP)"
        )
    )
    connection.execute(
        text(
            "INSERT INTO rag_documents "
            "(id, organization_id, source_type, document_title, checked_at, "
            "content_hash, created_at) "
            "VALUES "
            "('rag_doc_a', 'org_a', 'policy', 'Policy A', '2026-06-27', "
            "'hash-a', CURRENT_TIMESTAMP), "
            "('rag_doc_b', 'org_b', 'policy', 'Policy B', '2026-06-27', "
            "'hash-b', CURRENT_TIMESTAMP)"
        )
    )


def _assert_integrity_error(engine, sql: str) -> None:
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(text("PRAGMA foreign_keys=ON"))
            connection.execute(text(sql))
