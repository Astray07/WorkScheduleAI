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
    pair_unique_names = {
        item["name"] for item in inspector.get_unique_constraints("pair_constraints")
    }
    pair_check_names = {
        item["name"] for item in inspector.get_check_constraints("pair_constraints")
    }
    unavailability_check_names = {
        item["name"] for item in inspector.get_check_constraints("unavailabilities")
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

    assert "uq_employees_organization_employee_code" in employee_unique_names
    assert "uq_roles_organization_name" in role_unique_names
    assert (
        "uq_employee_roles_organization_employee_role"
        in employee_role_unique_names
    )
    assert "uq_pair_constraints_normalized_pair_type" in pair_unique_names
    assert "ck_pair_constraints_normalized_order" in pair_check_names
    assert "ck_unavailabilities_type" in unavailability_check_names
    assert "ck_unavailabilities_time_order" in unavailability_check_names
    assert (
        "uq_schedule_runs_organization_idempotency_key"
        in schedule_run_unique_names
    )
    assert "ck_schedule_runs_status" in schedule_run_check_names
    assert "ck_schedule_runs_recalculation_count" in schedule_run_check_names
    assert "uq_schedule_input_snapshots_schedule_run_id" in snapshot_unique_names
    assert "uq_override_approvals_run_proposal" in approval_unique_names
    assert "ck_override_approvals_type" in approval_check_names


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


def test_alembic_upgrade_head_stamps_expected_revision(tmp_path):
    db_path = tmp_path / "migration-test.sqlite"

    _upgrade_head(db_path)

    engine = create_engine(f"sqlite:///{db_path}", future=True)
    with engine.connect() as connection:
        version = connection.execute(
            text("select version_num from alembic_version")
        ).scalar_one()

    assert version == "20260624_0004"


def _upgrade_head(db_path: Path) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(config, "head")
