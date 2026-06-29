from collections.abc import Callable
from contextlib import AbstractContextManager
import json

from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import Session

from work_schedule_ai.api.dependencies import set_tenant_context
from work_schedule_ai.db.models import ScheduleRun, utc_now
from work_schedule_ai.worker.queue import ScheduleRunJob, ScheduleRunQueue

ScheduleRunExecutor = Callable[[Session, ScheduleRun], None]
ScheduleRunSessionFactory = Callable[[], AbstractContextManager[Session]]


def execute_schedule_run(
    db_session: Session,
    schedule_run_id: str,
    executor: ScheduleRunExecutor | None = None,
) -> ScheduleRun:
    run = _get_schedule_run(db_session, schedule_run_id)
    if run.status == "canceled":
        return run
    if run.status not in {"queued", "running"}:
        return run

    now = utc_now()
    run.status = "running"
    run.started_at = run.started_at or now
    run.updated_at = now
    db_session.flush()

    try:
        if executor is not None:
            executor(db_session, run)
    except Exception:
        db_session.rollback()
        failed_run = _get_schedule_run(db_session, schedule_run_id)
        finished_at = utc_now()
        if failed_run.status != "canceled":
            failed_run.status = "failed"
            failed_run.solver_status = "error"
            failed_run.solution_quality = "unknown"
            failed_run.started_at = failed_run.started_at or now
            failed_run.finished_at = finished_at
            failed_run.updated_at = finished_at
            db_session.commit()
        return failed_run

    finished_at = utc_now()
    if run.status == "running":
        run.status = "succeeded"
    if run.solver_status is None:
        run.solver_status = "not_started"
    if run.solution_quality == "unknown":
        run.solution_quality = "feasible_not_proven_optimal"
    run.finished_at = finished_at
    run.updated_at = finished_at
    db_session.commit()
    return run


def retry_schedule_run(
    db_session: Session,
    schedule_run_id: str,
) -> ScheduleRun:
    run = _get_schedule_run(db_session, schedule_run_id)
    if run.status == "canceled":
        return run
    run.current_attempt_no += 1
    run.status = "running"
    run.finished_at = None
    run.updated_at = utc_now()
    db_session.flush()
    return execute_schedule_run(db_session, schedule_run_id)


def cancel_schedule_run(
    db_session: Session,
    schedule_run_id: str,
) -> ScheduleRun:
    run = _get_schedule_run(db_session, schedule_run_id)
    if run.status not in {"queued", "running"}:
        raise InvalidRequestError(f"Cannot cancel ScheduleRun with status {run.status}")
    now = utc_now()
    run.status = "canceled"
    run.canceled_at = now
    run.updated_at = now
    db_session.commit()
    return run


def process_next_schedule_run(
    *,
    queue: ScheduleRunQueue,
    db_session_factory: ScheduleRunSessionFactory,
    executor: ScheduleRunExecutor | None = None,
    dequeue_timeout_seconds: int = 5,
) -> bool:
    job = queue.dequeue(timeout_seconds=dequeue_timeout_seconds)
    if job is None:
        return False
    job = _normalized_job(job)

    with db_session_factory() as db_session:
        if job.organization_id is not None:
            set_tenant_context(db_session, job.organization_id)
        try:
            execute_schedule_run(
                db_session,
                job.schedule_run_id,
                executor=executor,
            )
        except LookupError as exc:
            print(f"Skipping schedule run job: {exc}", flush=True)
    return True


def _normalized_job(job: ScheduleRunJob) -> ScheduleRunJob:
    try:
        parsed = json.loads(job.schedule_run_id)
    except json.JSONDecodeError:
        return job
    if not isinstance(parsed, dict):
        return job
    schedule_run_id = parsed.get("schedule_run_id")
    organization_id = parsed.get("organization_id")
    if not isinstance(schedule_run_id, str):
        return job
    return ScheduleRunJob(
        schedule_run_id=schedule_run_id,
        organization_id=(
            job.organization_id
            if job.organization_id is not None
            else organization_id if isinstance(organization_id, str) else None
        ),
    )


def _get_schedule_run(
    db_session: Session,
    schedule_run_id: str,
) -> ScheduleRun:
    run = db_session.get(ScheduleRun, schedule_run_id)
    if run is None:
        raise LookupError(f"ScheduleRun not found: {schedule_run_id}")
    return run
