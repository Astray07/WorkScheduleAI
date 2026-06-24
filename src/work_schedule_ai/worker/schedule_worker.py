from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import Session

from work_schedule_ai.db.models import ScheduleRun, utc_now


def execute_schedule_run(
    db_session: Session,
    schedule_run_id: str,
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

    finished_at = utc_now()
    run.status = "succeeded"
    run.solver_status = "not_started"
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


def _get_schedule_run(
    db_session: Session,
    schedule_run_id: str,
) -> ScheduleRun:
    run = db_session.get(ScheduleRun, schedule_run_id)
    if run is None:
        raise LookupError(f"ScheduleRun not found: {schedule_run_id}")
    return run
