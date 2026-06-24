from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.db.models import ScheduleRun


router = APIRouter(prefix="/operations", tags=["operations"])


SCHEDULE_RUN_STATUSES = (
    "queued",
    "running",
    "succeeded",
    "infeasible",
    "failed",
    "canceled",
)


class ScheduleRunMetricsResponse(BaseModel):
    total_runs: int
    active_runs: int
    status_counts: dict[str, int]
    completed_average_duration_seconds: float | None


@router.get(
    "/schedule-runs/metrics",
    response_model=ScheduleRunMetricsResponse,
)
def get_schedule_run_metrics(
    db_session: Session = Depends(get_db_session),
) -> ScheduleRunMetricsResponse:
    runs = list(db_session.execute(select(ScheduleRun)).scalars())
    status_counts = {status: 0 for status in SCHEDULE_RUN_STATUSES}
    durations: list[float] = []
    for run in runs:
        status_counts[run.status] = status_counts.get(run.status, 0) + 1
        if run.started_at is not None and run.finished_at is not None:
            durations.append((run.finished_at - run.started_at).total_seconds())

    return ScheduleRunMetricsResponse(
        total_runs=len(runs),
        active_runs=sum(status_counts[status] for status in ("queued", "running")),
        status_counts=status_counts,
        completed_average_duration_seconds=(
            round(sum(durations) / len(durations), 3) if durations else None
        ),
    )
