from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.db.models import Organization, SchedulePolicy, utc_now


router = APIRouter(prefix="/organizations", tags=["schedule-policies"])


class SchedulePolicyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    min_rest_hours: int = Field(ge=0, le=48)
    max_consecutive_shifts: int = Field(ge=1, le=31)
    max_shifts_per_week: int = Field(ge=1, le=14)
    weekend_shift_limit_per_month: int = Field(ge=0, le=31)
    night_shift_limit_per_month: int = Field(ge=0, le=31)
    default_unfilled_requirement_weight: int = Field(ge=0, le=10000)
    weight_workload_imbalance: int = Field(ge=0, le=10000)
    weight_pair_avoid_violation: int = Field(ge=0, le=10000)
    unfilled_policy: Literal["soft_penalty"]


class SchedulePolicyResponse(SchedulePolicyRequest):
    id: str
    organization_id: str


DEFAULT_POLICY = {
    "name": "기본 정책",
    "min_rest_hours": 11,
    "max_consecutive_shifts": 5,
    "max_shifts_per_week": 5,
    "weekend_shift_limit_per_month": 4,
    "night_shift_limit_per_month": 6,
    "default_unfilled_requirement_weight": 900,
    "weight_workload_imbalance": 100,
    "weight_pair_avoid_violation": 60,
    "unfilled_policy": "soft_penalty",
}


@router.get(
    "/{organization_id}/schedule-policy",
    response_model=SchedulePolicyResponse,
)
def get_schedule_policy(
    organization_id: str,
    db_session: Session = Depends(get_db_session),
) -> SchedulePolicyResponse:
    _get_organization_or_404(organization_id, db_session)
    policy = _get_policy(organization_id, db_session)
    if policy is None:
        policy = SchedulePolicy(
            id=_new_id("schedule_policy"),
            organization_id=organization_id,
            **DEFAULT_POLICY,
        )
        db_session.add(policy)
        db_session.commit()
    return _policy_response(policy)


@router.put(
    "/{organization_id}/schedule-policy",
    response_model=SchedulePolicyResponse,
)
def update_schedule_policy(
    organization_id: str,
    request: SchedulePolicyRequest,
    db_session: Session = Depends(get_db_session),
) -> SchedulePolicyResponse:
    _get_organization_or_404(organization_id, db_session)
    policy = _get_policy(organization_id, db_session)
    if policy is None:
        policy = SchedulePolicy(
            id=_new_id("schedule_policy"),
            organization_id=organization_id,
            **request.model_dump(),
        )
        db_session.add(policy)
    else:
        for field, value in request.model_dump().items():
            setattr(policy, field, value)
        policy.updated_at = utc_now()
    db_session.commit()
    return _policy_response(policy)


def _get_organization_or_404(
    organization_id: str,
    db_session: Session,
) -> Organization:
    organization = db_session.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    return organization


def _get_policy(
    organization_id: str,
    db_session: Session,
) -> SchedulePolicy | None:
    return db_session.execute(
        select(SchedulePolicy).where(SchedulePolicy.organization_id == organization_id)
    ).scalar_one_or_none()


def _policy_response(policy: SchedulePolicy) -> SchedulePolicyResponse:
    return SchedulePolicyResponse(
        id=policy.id,
        organization_id=policy.organization_id,
        name=policy.name,
        min_rest_hours=policy.min_rest_hours,
        max_consecutive_shifts=policy.max_consecutive_shifts,
        max_shifts_per_week=policy.max_shifts_per_week,
        weekend_shift_limit_per_month=policy.weekend_shift_limit_per_month,
        night_shift_limit_per_month=policy.night_shift_limit_per_month,
        default_unfilled_requirement_weight=policy.default_unfilled_requirement_weight,
        weight_workload_imbalance=policy.weight_workload_imbalance,
        weight_pair_avoid_violation=policy.weight_pair_avoid_violation,
        unfilled_policy=policy.unfilled_policy,
    )


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"
