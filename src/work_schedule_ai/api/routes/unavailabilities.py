from datetime import datetime
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.api.security import ADMIN_ROLES, READ_ROLES, require_roles
from work_schedule_ai.db.models import Employee, Organization, Unavailability


router = APIRouter(prefix="/organizations", tags=["unavailabilities"])


class UnavailabilityCreateRequest(BaseModel):
    employee_id: str
    type: Literal["vacation", "business_trip", "training", "personal"]
    starts_at: datetime
    ends_at: datetime
    override_allowed: bool
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class UnavailabilityResponse(UnavailabilityCreateRequest):
    id: str


@router.get(
    "/{organization_id}/unavailabilities",
    response_model=list[UnavailabilityResponse],
)
def list_unavailabilities(
    organization_id: str,
    db_session: Session = Depends(get_db_session),
) -> list[UnavailabilityResponse]:
    require_roles(db_session, READ_ROLES)
    _get_organization_or_404(organization_id, db_session)
    unavailabilities = db_session.execute(
        select(Unavailability)
        .where(Unavailability.organization_id == organization_id)
        .order_by(Unavailability.starts_at, Unavailability.id)
    ).scalars()
    return [
        _unavailability_response(unavailability)
        for unavailability in unavailabilities
    ]


@router.post(
    "/{organization_id}/unavailabilities",
    response_model=UnavailabilityResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_unavailability(
    organization_id: str,
    request: UnavailabilityCreateRequest,
    db_session: Session = Depends(get_db_session),
) -> UnavailabilityResponse:
    require_roles(db_session, ADMIN_ROLES)
    organization = db_session.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    employee = db_session.get(Employee, request.employee_id)
    if employee is None or employee.organization_id != organization_id:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_EMPLOYEE_ID",
                "message": "employee_id must belong to the organization.",
                "field": "employee_id",
            },
        )

    unavailability = Unavailability(
        id=_new_id("unavailability"),
        organization_id=organization_id,
        employee_id=request.employee_id,
        type=request.type,
        starts_at=request.starts_at,
        ends_at=request.ends_at,
        override_allowed=request.override_allowed,
        note=request.note,
    )
    db_session.add(unavailability)
    db_session.commit()

    return UnavailabilityResponse(
        id=unavailability.id,
        employee_id=request.employee_id,
        type=request.type,
        starts_at=request.starts_at,
        ends_at=request.ends_at,
        override_allowed=request.override_allowed,
        note=request.note,
    )


@router.patch(
    "/{organization_id}/unavailabilities/{unavailability_id}",
    response_model=UnavailabilityResponse,
)
def update_unavailability(
    organization_id: str,
    unavailability_id: str,
    request: UnavailabilityCreateRequest,
    db_session: Session = Depends(get_db_session),
) -> UnavailabilityResponse:
    require_roles(db_session, ADMIN_ROLES)
    _get_organization_or_404(organization_id, db_session)
    _get_employee_in_organization_or_422(
        organization_id,
        request.employee_id,
        db_session,
    )
    unavailability = db_session.get(Unavailability, unavailability_id)
    if unavailability is None or unavailability.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Unavailability not found")

    unavailability.employee_id = request.employee_id
    unavailability.type = request.type
    unavailability.starts_at = request.starts_at
    unavailability.ends_at = request.ends_at
    unavailability.override_allowed = request.override_allowed
    unavailability.note = request.note
    db_session.commit()
    return _unavailability_response(unavailability)


@router.delete(
    "/{organization_id}/unavailabilities/{unavailability_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_unavailability(
    organization_id: str,
    unavailability_id: str,
    db_session: Session = Depends(get_db_session),
) -> Response:
    require_roles(db_session, ADMIN_ROLES)
    _get_organization_or_404(organization_id, db_session)
    unavailability = db_session.get(Unavailability, unavailability_id)
    if unavailability is None or unavailability.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Unavailability not found")
    db_session.execute(
        delete(Unavailability).where(
            Unavailability.organization_id == organization_id,
            Unavailability.id == unavailability_id,
        )
    )
    db_session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


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


def _get_employee_in_organization_or_422(
    organization_id: str,
    employee_id: str,
    db_session: Session,
) -> Employee:
    employee = db_session.get(Employee, employee_id)
    if employee is None or employee.organization_id != organization_id:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_EMPLOYEE_ID",
                "message": "employee_id must belong to the organization.",
                "field": "employee_id",
            },
        )
    return employee


def _unavailability_response(
    unavailability: Unavailability,
) -> UnavailabilityResponse:
    return UnavailabilityResponse(
        id=unavailability.id,
        employee_id=unavailability.employee_id,
        type=unavailability.type,
        starts_at=unavailability.starts_at,
        ends_at=unavailability.ends_at,
        override_allowed=unavailability.override_allowed,
        note=unavailability.note,
    )
