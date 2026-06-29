from collections.abc import Generator
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from scripts.requeue_queued_schedule_runs import requeue_queued_schedule_runs
from work_schedule_ai.db.models import Base, Organization, ScheduleRun


def test_requeue_queued_schedule_runs_enqueues_only_queued_runs(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
):
    enqueued: list[tuple[str, str | None]] = []
    monkeypatch.setenv("WORKSCHEDULEAI_REQUEUE_ORGANIZATION_ID", "org_1")
    monkeypatch.setattr(
        "scripts.requeue_queued_schedule_runs.enqueue_schedule_run",
        lambda run_id, organization_id=None: enqueued.append((run_id, organization_id)),
    )
    db_session.add_all(
        [
            _run("run_queued", status="queued"),
            _run("run_succeeded", status="succeeded"),
        ]
    )
    db_session.commit()

    summary = requeue_queued_schedule_runs(db_session)

    assert summary.organization_id == "org_1"
    assert summary.requeued_count == 1
    assert summary.run_ids == ["run_queued"]
    assert enqueued == [("run_queued", "org_1")]


def test_requeue_queued_schedule_runs_recovers_stale_running_runs(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
):
    enqueued: list[tuple[str, str | None]] = []
    monkeypatch.setenv("WORKSCHEDULEAI_REQUEUE_ORGANIZATION_ID", "org_1")
    monkeypatch.setenv("WORKSCHEDULEAI_REQUEUE_STALE_RUNNING_MINUTES", "15")
    monkeypatch.setattr(
        "scripts.requeue_queued_schedule_runs.enqueue_schedule_run",
        lambda run_id, organization_id=None: enqueued.append((run_id, organization_id)),
    )
    stale_run = _run("run_stale", status="running")
    stale_run.updated_at = datetime.now(timezone.utc) - timedelta(minutes=30)
    fresh_run = _run("run_fresh", status="running")
    fresh_run.updated_at = datetime.now(timezone.utc)
    db_session.add_all([stale_run, fresh_run])
    db_session.commit()

    summary = requeue_queued_schedule_runs(db_session)

    assert summary.requeued_count == 1
    assert summary.run_ids == ["run_stale"]
    assert enqueued == [("run_stale", "org_1")]
    assert db_session.get(ScheduleRun, "run_stale").status == "queued"
    assert db_session.get(ScheduleRun, "run_fresh").status == "running"


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


def _run(run_id: str, *, status: str) -> ScheduleRun:
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
    )
