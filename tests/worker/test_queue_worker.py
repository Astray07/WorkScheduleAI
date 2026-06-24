from contextlib import nullcontext
from datetime import date
import importlib

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from work_schedule_ai.db.models import Base, Organization, ScheduleRun
from work_schedule_ai.worker.queue import InMemoryScheduleRunQueue


@pytest.fixture
def session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as db_session:
        db_session.add(Organization(id="org_1", name="Clinic A", timezone="Asia/Seoul"))
        db_session.commit()
        yield db_session


def test_run_queue_worker_processes_one_job_with_injected_dependencies(
    session: Session,
):
    try:
        queue_worker_module = importlib.import_module(
            "work_schedule_ai.worker.queue_worker"
        )
    except ModuleNotFoundError as exc:
        pytest.fail(f"queue worker module missing: {exc}")

    run = _queued_run()
    queue = InMemoryScheduleRunQueue()
    queue.enqueue(run.id)
    session.add(run)
    session.commit()

    def executor(db_session: Session, schedule_run: ScheduleRun) -> None:
        schedule_run.solver_status = "cp_sat_optimal"
        schedule_run.solution_quality = "optimal"
        db_session.flush()

    processed_count = queue_worker_module.run_queue_worker(
        queue=queue,
        db_session_factory=lambda: nullcontext(session),
        executor=executor,
        max_jobs=1,
        dequeue_timeout_seconds=0,
    )

    assert processed_count == 1
    assert run.status == "succeeded"
    assert run.solver_status == "cp_sat_optimal"


def test_run_queue_worker_returns_zero_when_no_job_is_available(
    session: Session,
):
    try:
        queue_worker_module = importlib.import_module(
            "work_schedule_ai.worker.queue_worker"
        )
    except ModuleNotFoundError as exc:
        pytest.fail(f"queue worker module missing: {exc}")

    processed_count = queue_worker_module.run_queue_worker(
        queue=InMemoryScheduleRunQueue(),
        db_session_factory=lambda: nullcontext(session),
        max_jobs=1,
        dequeue_timeout_seconds=0,
    )

    assert processed_count == 0


def _queued_run(status: str = "queued") -> ScheduleRun:
    return ScheduleRun(
        id="run_1",
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
