from __future__ import annotations

from datetime import datetime
import json
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.api.security import ADMIN_ROLES, READ_ROLES, require_roles
from work_schedule_ai.compliance import (
    LEGAL_DISCLAIMER,
    ComplianceAssignment,
    ComplianceWarning,
    compliance_warning_instance_key,
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
    employee_id: str | None = Field(default=None, max_length=120)
    slot_id: str | None = Field(default=None, max_length=120)
    week_key: str | None = Field(default=None, max_length=20)
    snapshot_hash: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=1, max_length=500)
    created_by_user_id: str | None = None


class ComplianceWarningOverrideResponse(BaseModel):
    id: str
    schedule_run_id: str
    warning_code: str
    employee_id: str | None
    slot_id: str | None
    week_key: str | None
    snapshot_hash: str
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
    require_roles(db_session, READ_ROLES)
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
    warnings_by_instance = {
        warning.instance_key: warning for warning in warnings
    }
    request_instance_key = compliance_warning_instance_key(
        warning_code=request.warning_code,
        employee_id=request.employee_id,
        slot_id=request.slot_id,
        week_key=request.week_key,
        snapshot_hash=request.snapshot_hash,
    )
    warning = warnings_by_instance.get(request_instance_key)
    if warning is None:
        raise HTTPException(
            status_code=422,
            detail="warning instance is not present on the current schedule run",
        )
    existing_override = db_session.execute(
        select(ComplianceWarningOverride).where(
            ComplianceWarningOverride.organization_id == organization_id,
            ComplianceWarningOverride.schedule_run_id == schedule_run_id,
            ComplianceWarningOverride.warning_code == request.warning_code,
            ComplianceWarningOverride.employee_id == _identity_db_value(
                warning.employee_id
            ),
            ComplianceWarningOverride.slot_id == _identity_db_value(warning.slot_id),
            ComplianceWarningOverride.week_key == _identity_db_value(
                warning.week_key
            ),
            ComplianceWarningOverride.snapshot_hash == warning.snapshot_hash,
        )
    ).scalar_one_or_none()
    if existing_override is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="warning instance already has an override",
        )
    now = utc_now()
    actor_user_id = (
        actor.user_id if actor.auth_required else request.created_by_user_id
    )
    override = ComplianceWarningOverride(
        id=_new_id("compliance_override"),
        organization_id=organization_id,
        schedule_run_id=schedule_run_id,
        warning_code=warning.code,
        employee_id=_identity_db_value(warning.employee_id),
        slot_id=_identity_db_value(warning.slot_id),
        week_key=_identity_db_value(warning.week_key),
        snapshot_hash=warning.snapshot_hash,
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
                    "warning_code": warning.code,
                    "employee_id": warning.employee_id,
                    "slot_id": warning.slot_id,
                    "week_key": warning.week_key,
                    "snapshot_hash": warning.snapshot_hash,
                    "instance_key": warning.instance_key,
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
        employee_id=_identity_api_value(override.employee_id),
        slot_id=_identity_api_value(override.slot_id),
        week_key=_identity_api_value(override.week_key),
        snapshot_hash=override.snapshot_hash,
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
            slot_id=_external_artifact_id(schedule_run_id, slot.id),
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


def _identity_db_value(value: str | None) -> str:
    return value or ""


def _identity_api_value(value: str) -> str | None:
    return value or None


def _external_artifact_id(run_id: str, stored_id: str) -> str:
    prefix = f"{run_id}__"
    return stored_id[len(prefix) :] if stored_id.startswith(prefix) else stored_id
