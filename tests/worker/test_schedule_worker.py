from datetime import date
from contextlib import nullcontext

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import Session

from work_schedule_ai.db.models import Base, Organization, ScheduleRun
from work_schedule_ai.worker import schedule_worker as schedule_worker_module
from work_schedule_ai.worker.queue import InMemoryScheduleRunQueue
from work_schedule_ai.worker.queue import ScheduleRunJob
from work_schedule_ai.worker.schedule_worker import (
    cancel_schedule_run,
    execute_schedule_run,
    retry_schedule_run,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as db_session:
        db_session.add(Organization(id="org_1", name="Clinic A", timezone="Asia/Seoul"))
        db_session.commit()
        yield db_session


def test_execute_schedule_run_transitions_queued_to_succeeded(session: Session):
    run = _queued_run()
    session.add(run)
    session.commit()

    result = execute_schedule_run(session, "run_1")

    assert result.status == "succeeded"
    assert result.current_attempt_no == 1
    assert result.recalculation_count == 0
    assert result.started_at is not None
    assert result.finished_at is not None


def test_execute_schedule_run_uses_executor_to_set_solver_status(session: Session):
    run = _queued_run()
    session.add(run)
    session.commit()

    def executor(db_session: Session, schedule_run: ScheduleRun) -> None:
        schedule_run.solver_status = "cp_sat_optimal"
        schedule_run.solution_quality = "optimal"
        db_session.flush()

    result = execute_schedule_run(session, "run_1", executor=executor)

    assert result.status == "succeeded"
    assert result.solver_status == "cp_sat_optimal"
    assert result.solution_quality == "optimal"


def test_execute_schedule_run_marks_failed_when_executor_raises(session: Session):
    run = _queued_run()
    session.add(run)
    session.commit()

    def executor(db_session: Session, schedule_run: ScheduleRun) -> None:
        raise RuntimeError("solver unavailable")

    result = execute_schedule_run(session, "run_1", executor=executor)

    assert result.status == "failed"
    assert result.solver_status == "error"
    assert result.solution_quality == "unknown"
    assert result.started_at is not None
    assert result.finished_at is not None


def test_cancel_schedule_run_marks_queued_run_canceled(session: Session):
    run = _queued_run()
    session.add(run)
    session.commit()

    result = cancel_schedule_run(session, "run_1")

    assert result.status == "canceled"
    assert result.canceled_at is not None


def test_execute_schedule_run_does_not_run_canceled_run(session: Session):
    run = _queued_run(status="canceled")
    session.add(run)
    session.commit()

    result = execute_schedule_run(session, "run_1")

    assert result.status == "canceled"
    assert result.started_at is None
    assert result.finished_at is None


def test_retry_schedule_run_increments_attempt_without_recalculation(session: Session):
    run = _queued_run(status="running")
    session.add(run)
    session.commit()

    result = retry_schedule_run(session, "run_1")

    assert result.status == "succeeded"
    assert result.current_attempt_no == 2
    assert result.recalculation_count == 0


def test_cancel_schedule_run_rejects_terminal_status(session: Session):
    run = _queued_run(status="succeeded")
    session.add(run)
    session.commit()

    with pytest.raises(InvalidRequestError, match="Cannot cancel"):
        cancel_schedule_run(session, "run_1")


def test_process_next_schedule_run_consumes_queue_and_executes_run(
    session: Session,
):
    run = _queued_run()
    queue = InMemoryScheduleRunQueue()
    queue.enqueue(run.id)
    session.add(run)
    session.commit()

    def executor(db_session: Session, schedule_run: ScheduleRun) -> None:
        schedule_run.solver_status = "cp_sat_optimal"
        schedule_run.solution_quality = "optimal"
        db_session.flush()

    processed = schedule_worker_module.process_next_schedule_run(
        queue=queue,
        db_session_factory=lambda: nullcontext(session),
        executor=executor,
        dequeue_timeout_seconds=0,
    )

    assert processed is True
    assert run.status == "succeeded"
    assert run.solver_status == "cp_sat_optimal"
    assert queue.dequeue(timeout_seconds=0) is None


def test_process_next_schedule_run_sets_tenant_context_from_job(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    run = _queued_run()
    queue = InMemoryScheduleRunQueue()
    queue.enqueue(run.id, organization_id="org_1")
    session.add(run)
    session.commit()
    tenant_contexts: list[str] = []

    def record_tenant_context(db_session: Session, organization_id: str) -> None:
        assert db_session is session
        tenant_contexts.append(organization_id)

    monkeypatch.setattr(
        schedule_worker_module,
        "set_tenant_context",
        record_tenant_context,
        raising=False,
    )

    processed = schedule_worker_module.process_next_schedule_run(
        queue=queue,
        db_session_factory=lambda: nullcontext(session),
        dequeue_timeout_seconds=0,
    )

    assert processed is True
    assert tenant_contexts == ["org_1"]


def test_process_next_schedule_run_accepts_raw_json_payload_from_stale_queue_parser(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    run = _queued_run()
    queue = _SingleJobQueue(
        ScheduleRunJob(
            schedule_run_id='{"organization_id":"org_1","schedule_run_id":"run_1"}'
        )
    )
    session.add(run)
    session.commit()
    tenant_contexts: list[str] = []

    monkeypatch.setattr(
        schedule_worker_module,
        "set_tenant_context",
        lambda _session, organization_id: tenant_contexts.append(organization_id),
        raising=False,
    )

    processed = schedule_worker_module.process_next_schedule_run(
        queue=queue,
        db_session_factory=lambda: nullcontext(session),
        dequeue_timeout_seconds=0,
    )

    assert processed is True
    assert tenant_contexts == ["org_1"]
    assert run.status == "succeeded"


def test_process_next_schedule_run_skips_missing_run_without_crashing(
    session: Session,
    capsys: pytest.CaptureFixture[str],
):
    queue = _SingleJobQueue(ScheduleRunJob(schedule_run_id="run_missing"))

    processed = schedule_worker_module.process_next_schedule_run(
        queue=queue,
        db_session_factory=lambda: nullcontext(session),
        dequeue_timeout_seconds=0,
    )

    assert processed is True
    assert "ScheduleRun not found: run_missing" in capsys.readouterr().out


def test_process_next_schedule_run_returns_false_when_queue_is_empty(
    session: Session,
):
    queue = InMemoryScheduleRunQueue()

    processed = schedule_worker_module.process_next_schedule_run(
        queue=queue,
        db_session_factory=lambda: nullcontext(session),
        dequeue_timeout_seconds=0,
    )

    assert processed is False


class _SingleJobQueue:
    def __init__(self, job: ScheduleRunJob) -> None:
        self.job = job

    def enqueue(
        self,
        schedule_run_id: str,
        *,
        organization_id: str | None = None,
    ) -> None:
        del schedule_run_id, organization_id
        raise NotImplementedError

    def dequeue(self, timeout_seconds: int = 5) -> ScheduleRunJob | None:
        del timeout_seconds
        job = self.job
        self.job = None
        return job


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
