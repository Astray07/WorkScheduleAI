from collections.abc import Generator
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from work_schedule_ai.api.app import create_app
from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.db.models import Base, Organization, ScheduleRun, utc_now


def test_schedule_run_metrics_reports_status_counts_and_durations(
    client: TestClient,
    db_session: Session,
):
    now = utc_now()
    db_session.add_all(
        [
            _run("run_queued", "queued"),
            _run("run_running", "running", started_at=now - timedelta(seconds=30)),
            _run(
                "run_succeeded",
                "succeeded",
                started_at=now - timedelta(seconds=20),
                finished_at=now,
            ),
            _run(
                "run_failed",
                "failed",
                started_at=now - timedelta(seconds=40),
                finished_at=now - timedelta(seconds=10),
            ),
        ]
    )
    db_session.commit()

    response = client.get("/operations/schedule-runs/metrics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_runs"] == 4
    assert payload["active_runs"] == 2
    assert payload["status_counts"] == {
        "queued": 1,
        "running": 1,
        "succeeded": 1,
        "infeasible": 0,
        "failed": 1,
        "canceled": 0,
    }
    assert payload["completed_average_duration_seconds"] == 25.0


def test_readiness_reports_database_and_redis_status(client: TestClient):
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "ok",
        "redis": "not_configured",
    }


def _run(
    run_id: str,
    status: str,
    *,
    started_at=None,
    finished_at=None,
) -> ScheduleRun:
    return ScheduleRun(
        id=run_id,
        organization_id="org_1",
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 7),
        template="one_shift_per_day",
        deterministic_mode=True,
        timeout_seconds=30,
        status=status,
        solver_status=None,
        solution_quality="unknown",
        current_attempt_no=1,
        recalculation_count=0,
        started_at=started_at,
        finished_at=finished_at,
    )


def _seed(session: Session) -> None:
    session.add(Organization(id="org_1", name="Clinic A", timezone="Asia/Seoul"))
    session.commit()


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
        _seed(session)
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
