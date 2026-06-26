from collections.abc import Generator

from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from work_schedule_ai.api.app import create_app
from work_schedule_ai.api.dependencies import get_db_session, set_tenant_context
from work_schedule_ai.api.security import enforce_organization_access
from work_schedule_ai.db.models import (
    Base,
    Employee,
    EmployeeUserLink,
    Membership,
    Organization,
    User,
)


def test_auth_required_rejects_missing_actor(monkeypatch):
    monkeypatch.setenv("WORKSCHEDULEAI_AUTH_REQUIRED", "1")
    client = _client()

    response = client.get("/organizations/org_1/roles")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTHENTICATION_REQUIRED"


def test_auth_required_allows_member(monkeypatch):
    monkeypatch.setenv("WORKSCHEDULEAI_AUTH_REQUIRED", "1")
    client = _client(seed_membership=True)

    response = client.get(
        "/organizations/org_1/roles",
        headers={"X-User-Id": "user_scheduler"},
    )

    assert response.status_code == 200


def test_auth_required_rejects_viewer_mutation(monkeypatch):
    monkeypatch.setenv("WORKSCHEDULEAI_AUTH_REQUIRED", "1")
    client = _client(seed_membership=True, role="viewer", user_id="user_viewer")

    response = client.post(
        "/organizations/org_1/demand-drivers",
        headers={"X-User-Id": "user_viewer"},
        json={
            "local_date": "2026-07-01",
            "segment": "day",
            "demand_count": 100,
            "required_staff_count": 4,
            "source": "manual",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ROLE_NOT_ALLOWED"


def test_auth_required_restricts_employee_request_to_linked_employee(monkeypatch):
    monkeypatch.setenv("WORKSCHEDULEAI_AUTH_REQUIRED", "1")
    client = _client(
        seed_membership=True,
        role="employee",
        user_id="user_employee",
        seed_employee_link=True,
    )

    own_response = client.post(
        "/organizations/org_1/employee-requests",
        headers={"X-User-Id": "user_employee"},
        json={
            "employee_id": "emp_1",
            "type": "unavailable",
            "starts_at": "2026-07-01T00:00:00+09:00",
            "ends_at": "2026-07-02T00:00:00+09:00",
            "note": "개인 일정",
        },
    )
    other_response = client.post(
        "/organizations/org_1/employee-requests",
        headers={"X-User-Id": "user_employee"},
        json={
            "employee_id": "emp_2",
            "type": "unavailable",
            "starts_at": "2026-07-01T00:00:00+09:00",
            "ends_at": "2026-07-02T00:00:00+09:00",
            "note": "다른 직원 요청",
        },
    )

    assert own_response.status_code == 201
    assert own_response.json()["requested_by_user_id"] == "user_employee"
    assert other_response.status_code == 403
    assert other_response.json()["detail"]["code"] == "EMPLOYEE_LINK_REQUIRED"


def test_auth_required_disables_global_metrics(monkeypatch):
    monkeypatch.setenv("WORKSCHEDULEAI_AUTH_REQUIRED", "1")
    client = _client(seed_membership=True)

    response = client.get("/operations/schedule-runs/metrics")

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "TENANT_SCOPE_REQUIRED"


def test_security_release_gate_reports_auth_mode(monkeypatch):
    monkeypatch.setenv("WORKSCHEDULEAI_AUTH_REQUIRED", "1")
    client = _client(seed_membership=True)

    response = client.get("/operations/security/release-gate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["auth_required"] is True
    assert payload["rbac_roles"] == ["owner", "admin", "scheduler", "viewer", "employee", "member"]
    assert payload["tenant_context_hook"] is True
    assert payload["public_saas_ready"] is False


def _client(
    seed_membership: bool = False,
    role: str = "scheduler",
    user_id: str = "user_scheduler",
    seed_employee_link: bool = False,
) -> TestClient:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(Organization(id="org_1", name="Clinic A", timezone="Asia/Seoul"))
    if seed_membership:
        session.add(User(id=user_id, email=f"{user_id}@example.com", name=user_id))
        session.add(
            Membership(
                organization_id="org_1",
                user_id=user_id,
                role=role,
            )
        )
    if seed_employee_link:
        session.add_all(
            [
                Employee(id="emp_1", organization_id="org_1", employee_code="E001", name="Kim"),
                Employee(id="emp_2", organization_id="org_1", employee_code="E002", name="Lee"),
                EmployeeUserLink(
                    id="link_1",
                    organization_id="org_1",
                    employee_id="emp_1",
                    user_id=user_id,
                    status="linked",
                ),
            ]
        )
    session.commit()
    app = create_app()

    def override_session(request: Request) -> Generator[Session, None, None]:
        organization_id = request.path_params.get("organization_id")
        if organization_id:
            set_tenant_context(session, organization_id)
            enforce_organization_access(session, request, organization_id)
        yield session

    app.dependency_overrides[get_db_session] = override_session
    return TestClient(app)
