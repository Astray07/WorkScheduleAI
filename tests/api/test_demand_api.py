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
    assert payload["staffing_status"] == "under_staffed"
    assert payload["staffing_variance_count"] == -1
    assert db_session.query(DemandDriver).count() == 1
    assert db_session.query(LaborBudget).count() == 1


def test_demand_and_budget_preview_reports_over_budget_and_over_staffed(
    client: TestClient,
):
    demand_response = client.post(
        "/organizations/org_1/demand-drivers",
        json={
            "local_date": "2026-07-02",
            "segment": "day",
            "demand_count": 80,
            "required_staff_count": 2,
            "source": "manual",
        },
    )
    assert demand_response.status_code == 201
    budget_response = client.post(
        "/organizations/org_1/labor-budgets",
        json={
            "period_start": "2026-07-01",
            "period_end": "2026-07-07",
            "budget_amount_cents": 100000,
            "currency": "KRW",
        },
    )
    assert budget_response.status_code == 201

    preview_response = client.get(
        "/organizations/org_1/demand-cost-preview",
        params={
            "period_start": "2026-07-01",
            "period_end": "2026-07-07",
            "planned_staff_count": 3,
            "hourly_rate_cents": 50000,
            "hours_per_shift": 2,
        },
    )

    assert preview_response.status_code == 200
    payload = preview_response.json()
    assert payload["required_staff_count"] == 2
    assert payload["planned_staff_count"] == 3
    assert payload["under_staffed_count"] == 0
    assert payload["over_staffed_count"] == 1
    assert payload["staffing_status"] == "over_staffed"
    assert payload["staffing_variance_count"] == 1
    assert payload["planned_cost_cents"] == 300000
    assert payload["budget_amount_cents"] == 100000
    assert payload["budget_variance_cents"] == -200000
    assert payload["budget_status"] == "over_budget"


def test_demand_and_budget_preview_reports_no_budget_and_matched_staffing(
    client: TestClient,
):
    demand_response = client.post(
        "/organizations/org_1/demand-drivers",
        json={
            "local_date": "2026-07-03",
            "segment": "day",
            "demand_count": 40,
            "required_staff_count": 2,
            "source": "manual",
        },
    )
    assert demand_response.status_code == 201

    preview_response = client.get(
        "/organizations/org_1/demand-cost-preview",
        params={
            "period_start": "2026-07-01",
            "period_end": "2026-07-07",
            "planned_staff_count": 2,
            "hourly_rate_cents": 50000,
            "hours_per_shift": 2,
        },
    )

    assert preview_response.status_code == 200
    payload = preview_response.json()
    assert payload["staffing_status"] == "matched"
    assert payload["staffing_variance_count"] == 0
    assert payload["planned_cost_cents"] == 200000
    assert payload["budget_amount_cents"] is None
    assert payload["budget_variance_cents"] is None
    assert payload["budget_status"] == "no_budget"


def test_demand_and_budget_preview_returns_optimization_policy_without_solver_mutation(
    client: TestClient,
):
    demand_response = client.post(
        "/organizations/org_1/demand-drivers",
        json={
            "local_date": "2026-07-04",
            "segment": "day",
            "demand_count": 160,
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
            "budget_amount_cents": 100000,
            "currency": "KRW",
        },
    )
    assert budget_response.status_code == 201

    preview_response = client.get(
        "/organizations/org_1/demand-cost-preview",
        params={
            "period_start": "2026-07-01",
            "period_end": "2026-07-07",
            "planned_staff_count": 3,
            "hourly_rate_cents": 50000,
            "hours_per_shift": 2,
            "under_staffing_penalty_per_shift": 120,
            "over_staffing_penalty_per_shift": 40,
            "budget_constraint_mode": "warning",
        },
    )

    assert preview_response.status_code == 200
    payload = preview_response.json()
    assert payload["under_staffed_count"] == 2
    assert payload["staffing_penalty_score"] == 240
    assert payload["optimization_policy"] == {
        "under_staffing_penalty_per_shift": 120,
        "over_staffing_penalty_per_shift": 40,
        "budget_constraint_mode": "warning",
        "solver_integration_status": "preview_only",
        "solver_objective_applied": False,
    }
    assert payload["budget_policy_violation"] is True
    assert payload["budget_constraint_status"] == "warning"


def test_demand_and_budget_preview_reports_blocking_budget_constraint_status(
    client: TestClient,
):
    budget_response = client.post(
        "/organizations/org_1/labor-budgets",
        json={
            "period_start": "2026-07-01",
            "period_end": "2026-07-07",
            "budget_amount_cents": 100000,
            "currency": "KRW",
        },
    )
    assert budget_response.status_code == 201

    preview_response = client.get(
        "/organizations/org_1/demand-cost-preview",
        params={
            "period_start": "2026-07-01",
            "period_end": "2026-07-07",
            "planned_staff_count": 3,
            "hourly_rate_cents": 50000,
            "hours_per_shift": 2,
            "budget_constraint_mode": "hard_constraint",
        },
    )

    assert preview_response.status_code == 200
    payload = preview_response.json()
    assert payload["budget_status"] == "over_budget"
    assert payload["budget_policy_violation"] is True
    assert payload["budget_constraint_status"] == "blocking"
    assert payload["optimization_policy"]["solver_objective_applied"] is False


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
