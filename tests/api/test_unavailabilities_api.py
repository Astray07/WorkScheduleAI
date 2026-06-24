from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from work_schedule_ai.api.app import create_app
from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.db.models import Base, Employee, Organization, Unavailability


STARTS_AT = "2026-07-01T00:00:00+09:00"
ENDS_AT = "2026-07-02T00:00:00+09:00"


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
                Organization(
                    id="org_1",
                    name="Clinic A",
                    timezone="Asia/Seoul",
                ),
                Organization(
                    id="org_2",
                    name="Clinic B",
                    timezone="Asia/Seoul",
                ),
                Employee(
                    id="emp_1",
                    organization_id="org_1",
                    employee_code="E001",
                    name="Kim",
                ),
                Employee(
                    id="emp_2",
                    organization_id="org_2",
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


def test_create_unavailability_persists_record(
    client: TestClient,
    db_session: Session,
):
    response = client.post(
        "/organizations/org_1/unavailabilities",
        json={
            "employee_id": "emp_1",
            "type": "vacation",
            "starts_at": STARTS_AT,
            "ends_at": ENDS_AT,
            "override_allowed": False,
            "note": "Annual leave",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["id"].startswith("unavailability_")
    assert payload["employee_id"] == "emp_1"
    assert payload["type"] == "vacation"
    assert payload["starts_at"] == STARTS_AT
    assert payload["ends_at"] == ENDS_AT
    assert payload["override_allowed"] is False
    assert payload["note"] == "Annual leave"
    unavailability = db_session.query(Unavailability).one()
    assert unavailability.organization_id == "org_1"
    assert unavailability.employee_id == "emp_1"
    assert unavailability.type == "vacation"


def test_create_unavailability_rejects_empty_time_range(
    client: TestClient,
    db_session: Session,
):
    response = client.post(
        "/organizations/org_1/unavailabilities",
        json={
            "employee_id": "emp_1",
            "type": "vacation",
            "starts_at": STARTS_AT,
            "ends_at": STARTS_AT,
            "override_allowed": False,
        },
    )

    assert response.status_code == 422
    assert db_session.query(Unavailability).count() == 0


def test_create_unavailability_rejects_employee_from_other_organization(
    client: TestClient,
    db_session: Session,
):
    response = client.post(
        "/organizations/org_1/unavailabilities",
        json={
            "employee_id": "emp_2",
            "type": "vacation",
            "starts_at": STARTS_AT,
            "ends_at": ENDS_AT,
            "override_allowed": False,
        },
    )

    assert response.status_code == 422
    assert db_session.query(Unavailability).count() == 0
