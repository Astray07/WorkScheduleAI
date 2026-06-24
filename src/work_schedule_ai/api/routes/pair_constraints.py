from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.db.models import (
    Employee,
    Organization,
    PairConstraint,
    normalize_pair_employee_ids,
)


router = APIRouter(prefix="/organizations", tags=["pair-constraints"])


class PairConstraintCreateRequest(BaseModel):
    employee_a_id: str
    employee_b_id: str
    type: Literal["blocked", "avoid", "prefer"]
    severity: Literal["low", "medium", "high", "critical"] = "high"
    override_allowed: bool
    active: bool = True


class PairConstraintResponse(PairConstraintCreateRequest):
    id: str
    normalized_employee_a_id: str
    normalized_employee_b_id: str


@router.post(
    "/{organization_id}/pair-constraints",
    response_model=PairConstraintResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_pair_constraint(
    organization_id: str,
    request: PairConstraintCreateRequest,
    db_session: Session = Depends(get_db_session),
) -> PairConstraintResponse:
    organization = db_session.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    try:
        normalized_a, normalized_b = normalize_pair_employee_ids(
            request.employee_a_id,
            request.employee_b_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_PAIR",
                "message": str(exc),
                "field": "employee_b_id",
            },
        ) from exc

    employee_ids = {request.employee_a_id, request.employee_b_id}
    employees = db_session.execute(
        select(Employee).where(
            Employee.organization_id == organization_id,
            Employee.id.in_(employee_ids),
        )
    ).scalars()
    if {employee.id for employee in employees} != employee_ids:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_EMPLOYEE_ID",
                "message": "Both employees must belong to the organization.",
                "field": "employee_id",
            },
        )

    duplicate = db_session.execute(
        select(PairConstraint).where(
            PairConstraint.organization_id == organization_id,
            PairConstraint.normalized_employee_a_id == normalized_a,
            PairConstraint.normalized_employee_b_id == normalized_b,
            PairConstraint.type == request.type,
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "PAIR_CONSTRAINT_DUPLICATE",
                "message": "Pair constraint already exists for this employee pair.",
                "field": "employee_a_id",
            },
        )

    pair_constraint = PairConstraint.create(
        id=_new_id("pair"),
        organization_id=organization_id,
        employee_a_id=request.employee_a_id,
        employee_b_id=request.employee_b_id,
        type=request.type,
        severity=request.severity,
        override_allowed=request.override_allowed,
        active=request.active,
    )
    db_session.add(pair_constraint)
    db_session.commit()

    return PairConstraintResponse(
        id=pair_constraint.id,
        employee_a_id=pair_constraint.employee_a_id,
        employee_b_id=pair_constraint.employee_b_id,
        type=pair_constraint.type,
        severity=pair_constraint.severity,
        override_allowed=pair_constraint.override_allowed,
        active=pair_constraint.active,
        normalized_employee_a_id=pair_constraint.normalized_employee_a_id,
        normalized_employee_b_id=pair_constraint.normalized_employee_b_id,
    )


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"
