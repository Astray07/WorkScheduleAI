from collections.abc import Generator
from datetime import date, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from work_schedule_ai.api.app import create_app
from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.api.signed_employee_links import (
    sign_employee_deep_link,
    verify_employee_deep_link,
)
from work_schedule_ai.db.models import (
    Base,
    Employee,
    Organization,
    PublicationAcknowledgement,
    PublicationNotification,
    SchedulePublication,
    ScheduleRun,
    utc_now,
)


def test_publication_acknowledgement_can_be_marked_acknowledged(
    client: TestClient,
    db_session: Session,
):
    response = client.post(
        "/organizations/org_1/schedule-publications/publication_1/acknowledgements/emp_1",
        json={"status": "acknowledged"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["employee_id"] == "emp_1"
    assert payload["status"] == "acknowledged"
    persisted = db_session.query(PublicationAcknowledgement).filter_by(id="ack_1").one()
    assert persisted.acknowledged_at is not None


def test_publication_acknowledgements_list_is_tenant_scoped(client: TestClient):
    response = client.get(
        "/organizations/org_1/schedule-publications/publication_1/acknowledgements"
    )

    assert response.status_code == 200
    assert [item["employee_id"] for item in response.json()["acknowledgements"]] == ["emp_1"]


def test_admin_can_create_signed_employee_publication_link(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("WORKSCHEDULEAI_EMPLOYEE_LINK_SECRET", "test-secret")

    response = client.post(
        "/organizations/org_1/schedule-publications/publication_1/employee-links/emp_1",
        json={"expires_in_hours": 24},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["organization_id"] == "org_1"
    assert payload["publication_id"] == "publication_1"
    assert payload["schedule_run_id"] == "run_1"
    assert payload["employee_id"] == "emp_1"
    parsed_employee_url = urlparse(payload["employee_url"])
    assert "token" not in parse_qs(parsed_employee_url.query)
    assert parse_qs(parsed_employee_url.fragment)["token"] == [payload["token"]]
    claims = verify_employee_deep_link(
        payload["token"],
        secret="test-secret",
        organization_id="org_1",
        publication_id="publication_1",
        employee_id="emp_1",
    )
    assert claims.employee_id == "emp_1"


def test_signed_employee_publication_link_rejects_cross_tenant_employee(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("WORKSCHEDULEAI_EMPLOYEE_LINK_SECRET", "test-secret")

    response = client.post(
        "/organizations/org_1/schedule-publications/publication_1/employee-links/emp_2",
        json={"expires_in_hours": 24},
    )

    assert response.status_code == 422


def test_signed_employee_publication_link_can_read_publication_context(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("WORKSCHEDULEAI_EMPLOYEE_LINK_SECRET", "test-secret")
    link_response = client.post(
        "/organizations/org_1/schedule-publications/publication_1/employee-links/emp_1",
        json={"expires_in_hours": 24},
    )

    response = client.get(
        "/employee/schedule-publications/publication_1",
        params={
            "organization_id": "org_1",
            "employee_id": "emp_1",
        },
        headers={"Authorization": f"Bearer {link_response.json()['token']}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["organization_id"] == "org_1"
    assert payload["publication_id"] == "publication_1"
    assert payload["schedule_run_id"] == "run_1"
    assert payload["employee_id"] == "emp_1"
    assert payload["employee_name"] == "Kim"
    assert payload["acknowledgement"]["status"] == "pending"
    assert [
        (item["notification_type"], item["channel"], item["status"])
        for item in payload["notifications"]
    ] == [
        ("published", "in_app", "pending_recorded"),
        ("changed", "in_app", "pending_recorded"),
    ]


def test_signed_employee_publication_link_can_acknowledge_publication(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("WORKSCHEDULEAI_EMPLOYEE_LINK_SECRET", "test-secret")
    link_response = client.post(
        "/organizations/org_1/schedule-publications/publication_1/employee-links/emp_1",
        json={"expires_in_hours": 24},
    )

    response = client.post(
        "/employee/schedule-publications/publication_1/acknowledgement",
        params={
            "organization_id": "org_1",
            "employee_id": "emp_1",
        },
        headers={"Authorization": f"Bearer {link_response.json()['token']}"},
        json={"status": "acknowledged"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["employee_id"] == "emp_1"
    assert payload["status"] == "acknowledged"
    persisted = db_session.query(PublicationAcknowledgement).filter_by(id="ack_1").one()
    assert persisted.acknowledged_at is not None


def test_signed_employee_publication_link_rejects_wrong_employee(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("WORKSCHEDULEAI_EMPLOYEE_LINK_SECRET", "test-secret")
    link_response = client.post(
        "/organizations/org_1/schedule-publications/publication_1/employee-links/emp_1",
        json={"expires_in_hours": 24},
    )

    response = client.get(
        "/employee/schedule-publications/publication_1",
        params={
            "organization_id": "org_1",
            "employee_id": "emp_2",
        },
        headers={"Authorization": f"Bearer {link_response.json()['token']}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "INVALID_EMPLOYEE_LINK_TOKEN"


def test_signed_employee_publication_link_rejects_query_token(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("WORKSCHEDULEAI_EMPLOYEE_LINK_SECRET", "test-secret")
    link_response = client.post(
        "/organizations/org_1/schedule-publications/publication_1/employee-links/emp_1",
        json={"expires_in_hours": 24},
    )

    response = client.get(
        "/employee/schedule-publications/publication_1",
        params={
            "organization_id": "org_1",
            "employee_id": "emp_1",
            "token": link_response.json()["token"],
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "EMPLOYEE_LINK_TOKEN_REQUIRED"


def test_signed_employee_publication_link_rejects_cross_tenant_public_api(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("WORKSCHEDULEAI_EMPLOYEE_LINK_SECRET", "test-secret")
    token = sign_employee_deep_link(
        secret="test-secret",
        organization_id="org_1",
        publication_id="publication_1",
        employee_id="emp_1",
        expires_at=utc_now() + timedelta(hours=1),
    )

    response = client.get(
        "/employee/schedule-publications/publication_2",
        params={
            "organization_id": "org_2",
            "employee_id": "emp_2",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["reason"] == "CLAIMS_MISMATCH"


def test_signed_employee_publication_link_rejects_expired_public_api_token(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("WORKSCHEDULEAI_EMPLOYEE_LINK_SECRET", "test-secret")
    token = sign_employee_deep_link(
        secret="test-secret",
        organization_id="org_1",
        publication_id="publication_1",
        employee_id="emp_1",
        expires_at=utc_now() - timedelta(minutes=1),
    )

    response = client.get(
        "/employee/schedule-publications/publication_1",
        params={
            "organization_id": "org_1",
            "employee_id": "emp_1",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["reason"] == "TOKEN_EXPIRED"


def test_signed_employee_publication_link_rejects_archived_publication(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("WORKSCHEDULEAI_EMPLOYEE_LINK_SECRET", "test-secret")
    publication = db_session.get(SchedulePublication, "publication_1")
    assert publication is not None
    publication.status = "archived"
    db_session.commit()
    token = sign_employee_deep_link(
        secret="test-secret",
        organization_id="org_1",
        publication_id="publication_1",
        employee_id="emp_1",
        expires_at=utc_now() + timedelta(hours=1),
    )

    response = client.get(
        "/employee/schedule-publications/publication_1",
        params={
            "organization_id": "org_1",
            "employee_id": "emp_1",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 410
    assert response.json()["detail"]["code"] == "PUBLICATION_NOT_AVAILABLE"


def test_signed_employee_publication_link_works_when_organization_auth_is_required(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("WORKSCHEDULEAI_AUTH_REQUIRED", "1")
    monkeypatch.setenv("WORKSCHEDULEAI_EMPLOYEE_LINK_SECRET", "test-secret")
    token = sign_employee_deep_link(
        secret="test-secret",
        organization_id="org_1",
        publication_id="publication_1",
        employee_id="emp_1",
        expires_at=utc_now() + timedelta(hours=1),
    )

    response = client.get(
        "/employee/schedule-publications/publication_1",
        params={
            "organization_id": "org_1",
            "employee_id": "emp_1",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["employee_id"] == "emp_1"


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
                Organization(id="org_2", name="Clinic B", timezone="Asia/Seoul"),
                Employee(id="emp_1", organization_id="org_1", employee_code="E001", name="Kim"),
                Employee(id="emp_2", organization_id="org_2", employee_code="E002", name="Lee"),
                _run("run_1", "org_1"),
                _run("run_2", "org_2"),
                _publication("publication_1", "org_1", "run_1"),
                _publication("publication_2", "org_2", "run_2"),
                PublicationAcknowledgement(
                    id="ack_1",
                    organization_id="org_1",
                    publication_id="publication_1",
                    employee_id="emp_1",
                    status="pending",
                ),
                PublicationAcknowledgement(
                    id="ack_2",
                    organization_id="org_2",
                    publication_id="publication_2",
                    employee_id="emp_2",
                    status="pending",
                ),
                PublicationNotification(
                    id="notification_1",
                    organization_id="org_1",
                    publication_id="publication_1",
                    employee_id="emp_1",
                    notification_type="published",
                    channel="in_app",
                    status="pending_recorded",
                ),
                PublicationNotification(
                    id="notification_2",
                    organization_id="org_1",
                    publication_id="publication_1",
                    employee_id="emp_1",
                    notification_type="changed",
                    channel="in_app",
                    status="pending_recorded",
                ),
                PublicationNotification(
                    id="notification_3",
                    organization_id="org_2",
                    publication_id="publication_2",
                    employee_id="emp_2",
                    notification_type="published",
                    channel="in_app",
                    status="pending_recorded",
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


def _run(run_id: str, organization_id: str) -> ScheduleRun:
    return ScheduleRun(
        id=run_id,
        organization_id=organization_id,
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 7),
        template="one_shift_per_day",
        deterministic_mode=True,
        timeout_seconds=30,
        status="succeeded",
        solver_status="cp_sat_optimal",
        solution_quality="optimal",
        current_attempt_no=1,
        recalculation_count=0,
    )


def _publication(publication_id: str, organization_id: str, run_id: str) -> SchedulePublication:
    return SchedulePublication(
        id=publication_id,
        organization_id=organization_id,
        schedule_run_id=run_id,
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 7),
        status="published",
        assignment_snapshot_hash="assignment_hash",
        issue_snapshot_hash="issue_hash",
    )
