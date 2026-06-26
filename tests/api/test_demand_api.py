from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from work_schedule_ai.api.app import create_app
from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.db.models import Base, DemandDriver, LaborBudget, Organization


def test_demand_and_budget_preview_reports_staffing_and_cost_gap(
    client: TestClient,
    db_session: Session,
):
    demand_response = client.post(
        "/organizations/org_1/demand-drivers",
        json={
            "local_date": "2026-07-01",
            "segment": "day",
            "demand_count": 120,
            "required_staff_count": 5,
            "source": "manual",
        },
    )
    assert demand_response.status_code == 201
    budget_response = client.post(
        "/organizations/org_1/labor-budgets",
        json={
            "period_start": "2026-07-01",
            "period_end": "2026-07-07",
            "budget_amount_cents": 800000,
            "currency": "KRW",
        },
    )
    assert budget_response.status_code == 201

    preview_response = client.get(
        "/organizations/org_1/demand-cost-preview",
        params={
            "period_start": "2026-07-01",
            "period_end": "2026-07-07",
            "planned_staff_count": 4,
            "hourly_rate_cents": 15000,
            "hours_per_shift": 8,
        },
    )

    assert preview_response.status_code == 200
    payload = preview_response.json()
    assert payload["required_staff_count"] == 5
    assert payload["planned_staff_count"] == 4
    assert payload["under_staffed_count"] == 1
    assert payload["planned_cost_cents"] == 480000
    assert payload["budget_status"] == "within_budget"
    assert db_session.query(DemandDriver).count() == 1
    assert db_session.query(LaborBudget).count() == 1


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
        session.add(Organization(id="org_1", name="Clinic A", timezone="Asia/Seoul"))
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
