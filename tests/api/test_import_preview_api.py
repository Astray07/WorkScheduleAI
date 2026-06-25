from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from work_schedule_ai.api.app import create_app
from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.db.models import Base, Employee, Organization, Role


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
                ),
                Employee(
                    id="emp_2",
                    organization_id="org_1",
                    employee_code="E002",
                    name="Lee",
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


def test_preview_employee_import_returns_rows_and_errors(client: TestClient):
    response = client.post(
        "/organizations/org_1/imports/preview",
        json={
            "type": "employees",
            "content": (
                "employee_code,name,roles,max_shifts_per_week\n"
                "E001,Kim,사수,5\n"
                "E002,,부사수,5"
            ),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert payload["rows"][0]["employee_code"] == "E001"
    assert payload["errors"][0]["row_no"] == 2
    assert payload["errors"][0]["field"] == "name"


def test_apply_employee_import_uses_bulk_upsert(client: TestClient):
    response = client.post(
        "/organizations/org_1/imports/apply",
        json={
            "type": "employees",
            "mode": "upsert",
            "content": (
                "employee_code,name,roles,max_shifts_per_week\n"
                "E003,Park,사수|부사수,5"
            ),
        },
    )

    assert response.status_code == 200
    assert response.json()["valid"] is True
    employees = client.get("/organizations/org_1/employees").json()
    assert [employee["employee_code"] for employee in employees] == [
        "E001",
        "E002",
        "E003",
    ]


def test_preview_employee_import_rejects_negative_weekly_cap(client: TestClient):
    response = client.post(
        "/organizations/org_1/imports/preview",
        json={
            "type": "employees",
            "content": (
                "employee_code,name,roles,max_shifts_per_week\n"
                "E003,Park,사수,-1"
            ),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert payload["errors"] == [
        {
            "field": "max_shifts_per_week",
            "row_no": 1,
            "code": "INVALID_RANGE",
            "message": "max_shifts_per_week must be between 0 and 31.",
        }
    ]


def test_apply_unavailability_import_uses_employee_code(client: TestClient):
    response = client.post(
        "/organizations/org_1/imports/apply",
        json={
            "type": "unavailabilities",
            "mode": "upsert",
            "content": (
                "employee_code,type,starts_at,ends_at,override_allowed\n"
                "E001,vacation,2026-07-01T00:00:00+09:00,2026-07-02T00:00:00+09:00,false"
            ),
        },
    )

    assert response.status_code == 200
    assert response.json()["valid"] is True
    assert client.get("/organizations/org_1/unavailabilities").json()[0]["employee_id"] == "emp_1"


def test_apply_pair_constraint_import_uses_employee_codes(client: TestClient):
    response = client.post(
        "/organizations/org_1/imports/apply",
        json={
            "type": "pair_constraints",
            "mode": "upsert",
            "content": (
                "employee_code_a,employee_code_b,type,severity,override_allowed\n"
                "E001,E002,blocked,high,true"
            ),
        },
    )

    assert response.status_code == 200
    assert response.json()["valid"] is True
    assert client.get("/organizations/org_1/pair-constraints").json()[0]["employee_a_id"] == "emp_1"


def test_preview_policy_import_parses_key_value_rows(client: TestClient):
    response = client.post(
        "/organizations/org_1/imports/preview",
        json={
            "type": "policy",
            "content": "key,value\nmin_rest_hours,10\nmax_consecutive_shifts,4",
        },
    )

    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_apply_policy_import_updates_policy(client: TestClient):
    response = client.post(
        "/organizations/org_1/imports/apply",
        json={
            "type": "policy",
            "mode": "upsert",
            "content": "key\tvalue\nmin_rest_hours\t10\nmax_consecutive_shifts\t4",
        },
    )

    assert response.status_code == 200
    assert response.json()["valid"] is True
    policy = client.get("/organizations/org_1/schedule-policy").json()
    assert policy["min_rest_hours"] == 10
    assert policy["max_consecutive_shifts"] == 4


def test_preview_policy_import_rejects_values_outside_api_contract(client: TestClient):
    response = client.post(
        "/organizations/org_1/imports/preview",
        json={
            "type": "policy",
            "content": (
                "key,value\n"
                "min_rest_hours,-1\n"
                "max_consecutive_shifts,99\n"
                "weight_pair_avoid_violation,10001"
            ),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert payload["errors"] == [
        {
            "field": "value",
            "row_no": 1,
            "code": "INVALID_RANGE",
            "message": "min_rest_hours must be between 0 and 48.",
        },
        {
            "field": "value",
            "row_no": 2,
            "code": "INVALID_RANGE",
            "message": "max_consecutive_shifts must be between 1 and 31.",
        },
        {
            "field": "value",
            "row_no": 3,
            "code": "INVALID_RANGE",
            "message": "weight_pair_avoid_violation must be between 0 and 10000.",
        },
    ]
