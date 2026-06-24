from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from work_schedule_ai.api.app import create_app
from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.db.models import Base, Employee, Organization, PairConstraint


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
                    id="emp_a",
                    organization_id="org_1",
                    employee_code="E001",
                    name="Kim",
                ),
                Employee(
                    id="emp_b",
                    organization_id="org_1",
                    employee_code="E002",
                    name="Lee",
                ),
                Employee(
                    id="emp_c",
                    organization_id="org_2",
                    employee_code="E003",
                    name="Park",
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


def test_create_pair_constraint_normalizes_and_persists_record(
    client: TestClient,
    db_session: Session,
):
    response = client.post(
        "/organizations/org_1/pair-constraints",
        json={
            "employee_a_id": "emp_b",
            "employee_b_id": "emp_a",
            "type": "blocked",
            "override_allowed": True,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["id"].startswith("pair_")
    assert payload["employee_a_id"] == "emp_b"
    assert payload["employee_b_id"] == "emp_a"
    assert payload["type"] == "blocked"
    assert payload["severity"] == "high"
    assert payload["override_allowed"] is True
    assert payload["active"] is True
    assert payload["normalized_employee_a_id"] == "emp_a"
    assert payload["normalized_employee_b_id"] == "emp_b"
    pair_constraint = db_session.query(PairConstraint).one()
    assert pair_constraint.normalized_employee_a_id == "emp_a"
    assert pair_constraint.normalized_employee_b_id == "emp_b"


def test_create_pair_constraint_rejects_self_pair(
    client: TestClient,
    db_session: Session,
):
    response = client.post(
        "/organizations/org_1/pair-constraints",
        json={
            "employee_a_id": "emp_a",
            "employee_b_id": "emp_a",
            "type": "blocked",
            "override_allowed": True,
        },
    )

    assert response.status_code == 422
    assert db_session.query(PairConstraint).count() == 0


def test_create_pair_constraint_rejects_employee_from_other_organization(
    client: TestClient,
    db_session: Session,
):
    response = client.post(
        "/organizations/org_1/pair-constraints",
        json={
            "employee_a_id": "emp_a",
            "employee_b_id": "emp_c",
            "type": "blocked",
            "override_allowed": True,
        },
    )

    assert response.status_code == 422
    assert db_session.query(PairConstraint).count() == 0


def test_create_pair_constraint_rejects_inverse_duplicate(
    client: TestClient,
    db_session: Session,
):
    first_response = client.post(
        "/organizations/org_1/pair-constraints",
        json={
            "employee_a_id": "emp_a",
            "employee_b_id": "emp_b",
            "type": "blocked",
            "override_allowed": True,
        },
    )
    second_response = client.post(
        "/organizations/org_1/pair-constraints",
        json={
            "employee_a_id": "emp_b",
            "employee_b_id": "emp_a",
            "type": "blocked",
            "override_allowed": True,
        },
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert db_session.query(PairConstraint).count() == 1
