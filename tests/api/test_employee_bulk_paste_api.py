from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from work_schedule_ai.api.app import create_app
from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.db.models import Base, Employee, EmployeeRole, Organization, Role


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            Organization(
                id="org_1",
                name="Demo Clinic",
                timezone="Asia/Seoul",
            )
        )
        session.add_all(
            [
                Role(id="role_senior", organization_id="org_1", name="사수"),
                Role(id="role_junior", organization_id="org_1", name="부사수"),
            ]
        )
        session.commit()
        yield session


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_session() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_validate_only_returns_success_without_persisting_employees(
    client: TestClient,
    db_session: Session,
):
    response = client.post(
        "/organizations/org_1/employees/bulk-paste",
        json={
            "mode": "validate_only",
            "rows": [
                {
                    "row_no": 1,
                    "employee_code": "E001",
                    "name": "Kim",
                    "role_names": ["사수"],
                },
                {
                    "row_no": 2,
                    "employee_code": "E002",
                    "name": "Lee",
                    "role_names": ["부사수"],
                },
            ],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "valid": True,
        "created_count": 0,
        "updated_count": 0,
        "errors": [],
        "employees": [],
    }
    assert db_session.query(Employee).count() == 0
    assert db_session.query(EmployeeRole).count() == 0


def test_upsert_creates_employees_and_role_links(
    client: TestClient,
    db_session: Session,
):
    response = client.post(
        "/organizations/org_1/employees/bulk-paste",
        json={
            "mode": "upsert",
            "rows": [
                {
                    "row_no": 1,
                    "employee_code": "E001",
                    "name": "Kim",
                    "role_names": ["사수"],
                },
                {
                    "row_no": 2,
                    "employee_code": "E002",
                    "name": "Lee",
                    "role_names": ["사수", "부사수"],
                },
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is True
    assert payload["created_count"] == 2
    assert payload["updated_count"] == 0
    assert payload["errors"] == []
    assert [employee["employee_code"] for employee in payload["employees"]] == [
        "E001",
        "E002",
    ]
    assert all(employee["id"].startswith("emp_") for employee in payload["employees"])
    assert db_session.query(Employee).count() == 2
    assert db_session.query(EmployeeRole).count() == 3


def test_duplicate_employee_code_returns_row_error_without_writes(
    client: TestClient,
    db_session: Session,
):
    response = client.post(
        "/organizations/org_1/employees/bulk-paste",
        json={
            "mode": "upsert",
            "rows": [
                {
                    "row_no": 1,
                    "employee_code": "E001",
                    "name": "Kim",
                    "role_names": ["사수"],
                },
                {
                    "row_no": 2,
                    "employee_code": "E001",
                    "name": "Lee",
                    "role_names": ["부사수"],
                },
            ],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "valid": False,
        "created_count": 0,
        "updated_count": 0,
        "errors": [
            {
                "code": "DUPLICATE_EMPLOYEE_CODE",
                "message": "employee_code is duplicated in the pasted rows.",
                "field": "employee_code",
                "row_no": 2,
            }
        ],
        "employees": [],
    }
    assert db_session.query(Employee).count() == 0
    assert db_session.query(EmployeeRole).count() == 0


def test_unknown_role_returns_row_error_without_writes(
    client: TestClient,
    db_session: Session,
):
    response = client.post(
        "/organizations/org_1/employees/bulk-paste",
        json={
            "mode": "upsert",
            "rows": [
                {
                    "row_no": 1,
                    "employee_code": "E001",
                    "name": "Kim",
                    "role_names": ["야간"],
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "valid": False,
        "created_count": 0,
        "updated_count": 0,
        "errors": [
            {
                "code": "UNKNOWN_ROLE",
                "message": "role_names contains a role that does not exist.",
                "field": "role_names",
                "row_no": 1,
            }
        ],
        "employees": [],
    }
    assert db_session.query(Employee).count() == 0
    assert db_session.query(EmployeeRole).count() == 0


def test_upsert_updates_existing_employee_and_replaces_roles(
    client: TestClient,
    db_session: Session,
):
    db_session.add(
        Employee(
            id="emp_existing",
            organization_id="org_1",
            employee_code="E001",
            name="Old Name",
            active=True,
        )
    )
    db_session.add(
        EmployeeRole(
            id="employee_role_existing",
            organization_id="org_1",
            employee_id="emp_existing",
            role_id="role_senior",
        )
    )
    db_session.commit()

    response = client.post(
        "/organizations/org_1/employees/bulk-paste",
        json={
            "mode": "upsert",
            "rows": [
                {
                    "row_no": 1,
                    "employee_code": "E001",
                    "name": "New Name",
                    "role_names": ["부사수"],
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["created_count"] == 0
    assert response.json()["updated_count"] == 1
    employee = db_session.query(Employee).filter_by(employee_code="E001").one()
    assert employee.name == "New Name"
    role_links = db_session.query(EmployeeRole).filter_by(employee_id="emp_existing").all()
    assert [role_link.role_id for role_link in role_links] == ["role_junior"]
