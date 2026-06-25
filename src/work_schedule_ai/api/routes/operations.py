from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.db.models import Assignment, AuditLog, Employee, ScheduleRun


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


class AuditLogEntryResponse(BaseModel):
    id: str
    actor_user_id: str | None
    action: str
    target_type: str
    target_id: str
    metadata: dict[str, Any]
    created_at: datetime


class AuditLogListResponse(BaseModel):
    organization_id: str
    entries: list[AuditLogEntryResponse]


class FairnessEmployeeRow(BaseModel):
    employee_id: str
    employee_code: str
    employee_name: str
    assignment_count: int
    delta_from_average: float


class FairnessSummaryResponse(BaseModel):
    organization_id: str
    schedule_run_id: str | None
    employee_count: int
    total_assignments: int
    average_assignments: float
    min_assignments: int
    max_assignments: int
    spread: int
    rows: list[FairnessEmployeeRow]


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


@router.get(
    "/organizations/{organization_id}/audit-logs",
    response_model=AuditLogListResponse,
)
def get_organization_audit_logs(
    organization_id: str,
    limit: int = 20,
    db_session: Session = Depends(get_db_session),
) -> AuditLogListResponse:
    bounded_limit = min(max(limit, 1), 100)
    logs = list(
        db_session.execute(
            select(AuditLog)
            .where(AuditLog.organization_id == organization_id)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(bounded_limit)
        ).scalars()
    )
    return AuditLogListResponse(
        organization_id=organization_id,
        entries=[
            AuditLogEntryResponse(
                id=log.id,
                actor_user_id=log.actor_user_id,
                action=log.action,
                target_type=log.target_type,
                target_id=log.target_id,
                metadata=_parse_metadata(log.metadata_json),
                created_at=log.created_at,
            )
            for log in logs
        ],
    )


@router.get(
    "/organizations/{organization_id}/fairness/summary",
    response_model=FairnessSummaryResponse,
)
def get_organization_fairness_summary(
    organization_id: str,
    schedule_run_id: str | None = None,
    db_session: Session = Depends(get_db_session),
) -> FairnessSummaryResponse:
    employees = list(
        db_session.execute(
            select(Employee)
            .where(Employee.organization_id == organization_id, Employee.active.is_(True))
            .order_by(Employee.employee_code)
        ).scalars()
    )
    counts = {employee.id: 0 for employee in employees}
    assignment_query = select(Assignment).where(
        Assignment.organization_id == organization_id,
    )
    if schedule_run_id is not None:
        assignment_query = assignment_query.where(
            Assignment.schedule_run_id == schedule_run_id,
        )
    for assignment in db_session.execute(assignment_query).scalars():
        if assignment.employee_id in counts:
            counts[assignment.employee_id] += 1

    employee_count = len(employees)
    total_assignments = sum(counts.values())
    average = round(total_assignments / employee_count, 3) if employee_count else 0.0
    min_assignments = min(counts.values()) if counts else 0
    max_assignments = max(counts.values()) if counts else 0

    rows = [
        FairnessEmployeeRow(
            employee_id=employee.id,
            employee_code=employee.employee_code,
            employee_name=employee.name,
            assignment_count=counts[employee.id],
            delta_from_average=round(counts[employee.id] - average, 3),
        )
        for employee in employees
    ]
    rows.sort(key=lambda row: (-row.assignment_count, row.employee_code))

    return FairnessSummaryResponse(
        organization_id=organization_id,
        schedule_run_id=schedule_run_id,
        employee_count=employee_count,
        total_assignments=total_assignments,
        average_assignments=average,
        min_assignments=min_assignments,
        max_assignments=max_assignments,
        spread=max_assignments - min_assignments,
        rows=rows,
    )


def _parse_metadata(raw_metadata: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_metadata)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
