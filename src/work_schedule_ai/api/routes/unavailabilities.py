from datetime import datetime
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from work_schedule_ai.api.dependencies import get_db_session
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


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"
