from collections.abc import Generator
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from work_schedule_ai.api.app import create_app
from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.db.models import (
    AuditLog,
    Base,
    Employee,
    EmployeeRequest,
    EmployeeUserLink,
    Organization,
    Unavailability,
    User,
)


def test_employee_request_approval_creates_unavailability_and_audit_log(
    client: TestClient,
    db_session: Session,
):
    link_response = client.post(
        "/organizations/org_1/employee-user-links",
        json={"employee_id": "emp_1", "user_id": "user_1", "status": "linked"},
    )
    assert link_response.status_code == 201

    submit_response = client.post(
        "/organizations/org_1/employee-requests",
        json={
            "employee_id": "emp_1",
            "requested_by_user_id": "user_1",
            "type": "unavailable",
            "starts_at": "2026-07-01T00:00:00+09:00",
            "ends_at": "2026-07-02T00:00:00+09:00",
            "note": "개인 일정",
        },
    )
    assert submit_response.status_code == 201
    request_id = submit_response.json()["id"]

    approve_response = client.post(
        f"/organizations/org_1/employee-requests/{request_id}/approve",
        json={"reviewed_by_user_id": "user_1", "reason": "운영 승인"},
    )

    assert approve_response.status_code == 200
    payload = approve_response.json()
    assert payload["status"] == "approved"
    assert payload["source_unavailability_id"]
    assert db_session.query(EmployeeUserLink).count() == 1
    assert db_session.query(EmployeeRequest).one().status == "approved"
    assert db_session.query(Unavailability).count() == 1
    assert db_session.query(AuditLog).filter_by(action="employee_request_approved").count() == 1


def test_employee_request_reject_keeps_solver_input_unchanged(
    client: TestClient,
    db_session: Session,
):
    submit_response = client.post(
        "/organizations/org_1/employee-requests",
        json={
            "employee_id": "emp_1",
            "requested_by_user_id": None,
            "type": "vacation",
            "starts_at": "2026-07-03T00:00:00+09:00",
            "ends_at": "2026-07-04T00:00:00+09:00",
            "note": None,
        },
    )
    request_id = submit_response.json()["id"]

    reject_response = client.post(
        f"/organizations/org_1/employee-requests/{request_id}/reject",
        json={"reviewed_by_user_id": None, "reason": "이미 인력 부족"},
    )

    assert reject_response.status_code == 200
    assert reject_response.json()["status"] == "rejected"
    assert db_session.query(Unavailability).count() == 0
    assert db_session.query(AuditLog).filter_by(action="employee_request_rejected").count() == 1


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
        session.add_all(
            [
                Organization(id="org_1", name="Clinic A", timezone="Asia/Seoul"),
                Employee(id="emp_1", organization_id="org_1", employee_code="E001", name="Kim"),
                User(id="user_1", email="employee@example.com", name="Kim"),
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
