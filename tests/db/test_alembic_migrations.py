from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


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
    pair_unique_names = {
        item["name"] for item in inspector.get_unique_constraints("pair_constraints")
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
    publication_check_names = {
        item["name"] for item in inspector.get_check_constraints("schedule_publications")
    }
    shift_type_unique_names = {
        item["name"] for item in inspector.get_unique_constraints("shift_types")
    }
    shift_requirement_unique_names = {
        item["name"] for item in inspector.get_unique_constraints("shift_requirements")
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
    assert "uq_pair_constraints_normalized_pair_type" in pair_unique_names
    assert "ck_pair_constraints_normalized_order" in pair_check_names
    assert "ck_unavailabilities_type" in unavailability_check_names
    assert "ck_unavailabilities_time_order" in unavailability_check_names
    assert "fk_unavailabilities_tenant_employee" in unavailability_fk_names
    assert (
        "uq_schedule_runs_organization_idempotency_key"
        in schedule_run_unique_names
    )
    assert "ck_schedule_runs_status" in schedule_run_check_names
    assert "ck_schedule_runs_recalculation_count" in schedule_run_check_names
    assert "uq_schedule_input_snapshots_schedule_run_id" in snapshot_unique_names
    assert "uq_override_approvals_run_proposal" in approval_unique_names
    assert "ck_override_approvals_type" in approval_check_names
    assert "uq_schedule_recalculations_run_idempotency_key" in recalc_unique_names
    assert "ck_schedule_recalculations_count" in recalc_check_names
    assert "uq_schedule_publications_schedule_run_id" in publication_unique_names
    assert "ck_schedule_publications_status" in publication_check_names
    assert "ck_schedule_publications_period_order" in publication_check_names
    assert "uq_shift_types_organization_name" in shift_type_unique_names
    assert (
        "uq_shift_requirements_shift_type_role"
        in shift_requirement_unique_names
    )
    assert "ck_shift_requirements_required_count" in shift_requirement_check_names
    assert "uq_schedule_policies_organization_id" in schedule_policy_unique_names
    assert "ck_schedule_policies_unfilled_policy" in schedule_policy_check_names
    assert (
        "uq_compliance_warning_overrides_instance"
        in compliance_override_unique_names
    )


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

    assert version == "20260626_0022"


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
