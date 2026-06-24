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

    assert "uq_employees_organization_employee_code" in employee_unique_names
    assert "uq_roles_organization_name" in role_unique_names
    assert (
        "uq_employee_roles_organization_employee_role"
        in employee_role_unique_names
    )
    assert "uq_pair_constraints_normalized_pair_type" in pair_unique_names
    assert "ck_pair_constraints_normalized_order" in pair_check_names


def test_alembic_upgrade_head_stamps_expected_revision(tmp_path):
    db_path = tmp_path / "migration-test.sqlite"

    _upgrade_head(db_path)

    engine = create_engine(f"sqlite:///{db_path}", future=True)
    with engine.connect() as connection:
        version = connection.execute(
            text("select version_num from alembic_version")
        ).scalar_one()

    assert version == "20260624_0001"


def _upgrade_head(db_path: Path) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(config, "head")

