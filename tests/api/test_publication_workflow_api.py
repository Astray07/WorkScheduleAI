from collections.abc import Generator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from work_schedule_ai.api.app import create_app
from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.api.signed_employee_links import verify_employee_deep_link
from work_schedule_ai.db.models import (
    Base,
    Employee,
    Organization,
    PublicationAcknowledgement,
    SchedulePublication,
    ScheduleRun,
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
    assert "token=" in payload["employee_url"]
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
