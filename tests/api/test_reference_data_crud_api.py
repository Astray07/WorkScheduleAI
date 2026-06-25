from collections.abc import Generator
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from work_schedule_ai.api.app import create_app
from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.db.models import (
    Base,
    Employee,
    EmployeeRole,
    Organization,
    PairConstraint,
    Role,
    ShiftRequirement,
    ShiftType,
    Unavailability,
)


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
        session.add(Organization(id="org_1", name="Demo Clinic", timezone="Asia/Seoul"))
        session.add_all(
            [
                Role(id="role_senior", organization_id="org_1", name="사수"),
                Role(id="role_junior", organization_id="org_1", name="부사수"),
                Employee(
                    id="emp_1",
                    organization_id="org_1",
                    employee_code="E001",
                    name="Kim",
                    max_shifts_per_week=5,
                ),
                Employee(
                    id="emp_2",
                    organization_id="org_1",
                    employee_code="E002",
                    name="Lee",
                    max_shifts_per_week=5,
                ),
            ]
        )
        session.add_all(
            [
                EmployeeRole(
                    id="employee_role_1",
                    organization_id="org_1",
                    employee_id="emp_1",
                    role_id="role_senior",
                ),
                EmployeeRole(
                    id="employee_role_2",
                    organization_id="org_1",
                    employee_id="emp_2",
                    role_id="role_junior",
                ),
            ]
        )
        session.add(
            Unavailability(
                id="unav_1",
                organization_id="org_1",
                employee_id="emp_1",
                type="vacation",
                starts_at=datetime.fromisoformat("2026-07-01T00:00:00+09:00"),
                ends_at=datetime.fromisoformat("2026-07-02T00:00:00+09:00"),
                override_allowed=False,
                note="Annual leave",
            )
        )
        session.add(
            PairConstraint.create(
                id="pair_1",
                organization_id="org_1",
                employee_a_id="emp_1",
                employee_b_id="emp_2",
                type="blocked",
                severity="high",
                override_allowed=True,
            )
        )
        shift_type = ShiftType(
            id="shift_type_1",
            organization_id="org_1",
            name="주간 근무",
            local_start_time="09:00",
            local_end_time="18:00",
            timezone="Asia/Seoul",
            crosses_midnight=False,
            active_weekdays="0,1,2,3,4",
            active=True,
        )
        session.add(shift_type)
        session.add_all(
            [
                ShiftRequirement(
                    id="shift_requirement_1",
                    organization_id="org_1",
                    shift_type_id="shift_type_1",
                    role_id="role_senior",
                    required_count=1,
                    unfilled_weight_override=None,
                ),
                ShiftRequirement(
                    id="shift_requirement_2",
                    organization_id="org_1",
                    shift_type_id="shift_type_1",
                    role_id="role_junior",
                    required_count=1,
                    unfilled_weight_override=None,
                ),
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


def test_list_roles_returns_default_roles(client: TestClient):
    response = client.get("/organizations/org_1/roles")

    assert response.status_code == 200
    assert [role["name"] for role in response.json()] == ["부사수", "사수"]


def test_list_employees_returns_role_names(client: TestClient):
    response = client.get("/organizations/org_1/employees")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["employee_code"] == "E001"
    assert payload[0]["role_names"] == ["사수"]
    assert payload[0]["max_shifts_per_week"] == 5


def test_update_employee_replaces_roles_and_weekly_cap(
    client: TestClient,
    db_session: Session,
):
    response = client.patch(
        "/organizations/org_1/employees/emp_1",
        json={
            "employee_code": "E001",
            "name": "Kim Updated",
            "active": True,
            "role_names": ["부사수"],
            "max_shifts_per_week": 4,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Kim Updated"
    assert payload["role_names"] == ["부사수"]
    employee = db_session.get(Employee, "emp_1")
    assert employee is not None
    assert employee.max_shifts_per_week == 4
    role_links = db_session.query(EmployeeRole).filter_by(employee_id="emp_1").all()
    assert [link.role_id for link in role_links] == ["role_junior"]


def test_delete_employee_deactivates_record(client: TestClient):
    response = client.delete("/organizations/org_1/employees/emp_1")

    assert response.status_code == 204
    list_response = client.get("/organizations/org_1/employees")
    payload = list_response.json()
    assert payload[0]["employee_code"] == "E001"
    assert payload[0]["active"] is False


def test_unavailability_list_update_delete(client: TestClient):
    list_response = client.get("/organizations/org_1/unavailabilities")
    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == "unav_1"

    update_response = client.patch(
        "/organizations/org_1/unavailabilities/unav_1",
        json={
            "employee_id": "emp_1",
            "type": "business_trip",
            "starts_at": "2026-07-03T00:00:00+09:00",
            "ends_at": "2026-07-04T00:00:00+09:00",
            "override_allowed": True,
            "note": "Updated",
        },
    )

    assert update_response.status_code == 200
    assert update_response.json()["type"] == "business_trip"
    delete_response = client.delete("/organizations/org_1/unavailabilities/unav_1")
    assert delete_response.status_code == 204
    assert client.get("/organizations/org_1/unavailabilities").json() == []


def test_pair_constraint_list_update_delete(client: TestClient):
    list_response = client.get("/organizations/org_1/pair-constraints")
    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == "pair_1"

    update_response = client.patch(
        "/organizations/org_1/pair-constraints/pair_1",
        json={
            "employee_a_id": "emp_1",
            "employee_b_id": "emp_2",
            "type": "avoid",
            "severity": "medium",
            "override_allowed": False,
            "active": True,
        },
    )

    assert update_response.status_code == 200
    assert update_response.json()["type"] == "avoid"
    delete_response = client.delete("/organizations/org_1/pair-constraints/pair_1")
    assert delete_response.status_code == 204
    assert client.get("/organizations/org_1/pair-constraints").json() == []


def test_shift_type_update_delete(client: TestClient):
    update_response = client.patch(
        "/organizations/org_1/shift-types/shift_type_1",
        json={
            "name": "야간 근무",
            "local_start_time": "22:00",
            "local_end_time": "06:00",
            "timezone": "Asia/Seoul",
            "crosses_midnight": True,
            "active_weekdays": [0, 1, 2, 3, 4],
            "active": True,
            "requirements": [
                {"role_id": "role_senior", "required_count": 1},
                {"role_id": "role_junior", "required_count": 2},
            ],
        },
    )

    assert update_response.status_code == 200
    payload = update_response.json()
    assert payload["name"] == "야간 근무"
    assert payload["requirements"][1]["required_count"] == 2
    delete_response = client.delete("/organizations/org_1/shift-types/shift_type_1")
    assert delete_response.status_code == 204
    list_response = client.get("/organizations/org_1/shift-types")
    assert list_response.json()[0]["active"] is False
