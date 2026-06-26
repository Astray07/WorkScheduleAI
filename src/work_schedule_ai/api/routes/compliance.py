from __future__ import annotations

from datetime import datetime
import json
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.api.security import ADMIN_ROLES, require_roles
from work_schedule_ai.compliance import (
    LEGAL_DISCLAIMER,
    ComplianceAssignment,
    ComplianceWarning,
    evaluate_compliance_warnings,
)
from work_schedule_ai.db.models import (
    Assignment,
    AuditLog,
    ComplianceWarningOverride,
    Organization,
    ScheduleRun,
    ShiftSlot,
    utc_now,
)


router = APIRouter(prefix="/organizations", tags=["compliance"])


class ComplianceWarningResponse(BaseModel):
    organization_id: str
    schedule_run_id: str
    legal_disclaimer: str
    warnings: list[ComplianceWarning]


class ComplianceWarningOverrideRequest(BaseModel):
    warning_code: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=500)
    created_by_user_id: str | None = None


class ComplianceWarningOverrideResponse(BaseModel):
    id: str
    schedule_run_id: str
    warning_code: str
    reason: str
    created_at: datetime


@router.get(
    "/{organization_id}/schedule-runs/{schedule_run_id}/compliance-warnings",
    response_model=ComplianceWarningResponse,
)
def get_compliance_warnings(
    organization_id: str,
    schedule_run_id: str,
    db_session: Session = Depends(get_db_session),
) -> ComplianceWarningResponse:
    _get_run_or_404(organization_id, schedule_run_id, db_session)
    return ComplianceWarningResponse(
        organization_id=organization_id,
        schedule_run_id=schedule_run_id,
        legal_disclaimer=LEGAL_DISCLAIMER,
        warnings=_warnings_for_run(organization_id, schedule_run_id, db_session),
    )


@router.post(
    "/{organization_id}/schedule-runs/{schedule_run_id}/compliance-warning-overrides",
    response_model=ComplianceWarningOverrideResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_compliance_warning_override(
    organization_id: str,
    schedule_run_id: str,
    request: ComplianceWarningOverrideRequest,
    db_session: Session = Depends(get_db_session),
) -> ComplianceWarningOverrideResponse:
    actor = require_roles(db_session, ADMIN_ROLES)
    _get_run_or_404(organization_id, schedule_run_id, db_session)
    warnings = _warnings_for_run(organization_id, schedule_run_id, db_session)
    if request.warning_code not in {warning.code for warning in warnings}:
        raise HTTPException(
            status_code=422,
            detail="warning_code is not present on the current schedule run",
        )
    now = utc_now()
    actor_user_id = (
        actor.user_id if actor.auth_required else request.created_by_user_id
    )
    override = ComplianceWarningOverride(
        id=_new_id("compliance_override"),
        organization_id=organization_id,
        schedule_run_id=schedule_run_id,
        warning_code=request.warning_code,
        reason=request.reason,
        created_by_user_id=actor_user_id,
        created_at=now,
    )
    db_session.add(override)
    db_session.add(
        AuditLog(
            id=_new_id("audit"),
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="compliance_warning_overridden",
            target_type="schedule_run",
            target_id=schedule_run_id,
            metadata_json=json.dumps(
                {
                    "warning_code": request.warning_code,
                    "reason": request.reason,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            created_at=now,
        )
    )
    db_session.commit()
    return ComplianceWarningOverrideResponse(
        id=override.id,
        schedule_run_id=schedule_run_id,
        warning_code=override.warning_code,
        reason=override.reason,
        created_at=override.created_at,
    )


def _warnings_for_run(
    organization_id: str,
    schedule_run_id: str,
    db_session: Session,
) -> list[ComplianceWarning]:
    rows = db_session.execute(
        select(Assignment, ShiftSlot)
        .join(ShiftSlot, ShiftSlot.id == Assignment.shift_slot_id)
        .where(
            Assignment.organization_id == organization_id,
            Assignment.schedule_run_id == schedule_run_id,
            ShiftSlot.organization_id == organization_id,
            ShiftSlot.schedule_run_id == schedule_run_id,
        )
    ).all()
    assignments = [
        ComplianceAssignment(
            employee_id=assignment.employee_id,
            employee_name=assignment.employee_name,
            slot_id=slot.id,
            local_date=slot.local_date.isoformat(),
            label=slot.label,
            starts_at=slot.starts_at,
            ends_at=slot.ends_at,
        )
        for assignment, slot in rows
    ]
    return evaluate_compliance_warnings(assignments)


def _get_run_or_404(
    organization_id: str,
    schedule_run_id: str,
    db_session: Session,
) -> ScheduleRun:
    organization = db_session.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    run = db_session.get(ScheduleRun, schedule_run_id)
    if run is None or run.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="ScheduleRun not found")
    return run


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"
