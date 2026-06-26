from __future__ import annotations

from datetime import date, datetime, timedelta
import json
import os
from typing import Literal
from urllib.parse import urlencode
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from work_schedule_ai.api.dependencies import get_db_session, set_tenant_context
from work_schedule_ai.api.security import ADMIN_ROLES, current_actor, require_roles
from work_schedule_ai.api.signed_employee_links import (
    EmployeeDeepLinkTokenError,
    sign_employee_deep_link,
    verify_employee_deep_link,
)
from work_schedule_ai.db.models import (
    AuditLog,
    Employee,
    EmployeeRequest,
    EmployeeUserLink,
    Organization,
    PublicationAcknowledgement,
    PublicationNotification,
    SchedulePublication,
    Unavailability,
    User,
    utc_now,
)


router = APIRouter(prefix="/organizations", tags=["employee-self-service"])
public_router = APIRouter(prefix="/employee", tags=["employee-self-service"])


class EmployeeUserLinkRequest(BaseModel):
    employee_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    status: Literal["invited", "linked", "disabled"]


class EmployeeUserLinkResponse(EmployeeUserLinkRequest):
    id: str
    organization_id: str


class EmployeeRequestCreate(BaseModel):
    employee_id: str = Field(min_length=1)
    requested_by_user_id: str | None = None
    type: Literal[
        "vacation",
        "unavailable",
        "prefer_shift",
        "avoid_shift",
        "swap",
        "open_shift",
    ]
    starts_at: datetime
    ends_at: datetime
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class EmployeeRequestReview(BaseModel):
    reviewed_by_user_id: str | None = None
    reason: str = Field(min_length=1, max_length=500)


class EmployeeRequestResponse(EmployeeRequestCreate):
    id: str
    organization_id: str
    status: str
    manager_reason: str | None
    reviewed_by_user_id: str | None
    reviewed_at: datetime | None
    source_unavailability_id: str | None
    created_at: datetime


class AcknowledgementUpdateRequest(BaseModel):
    status: Literal["acknowledged"]


class PublicationAcknowledgementResponse(BaseModel):
    id: str
    publication_id: str
    employee_id: str
    status: str
    acknowledged_at: datetime | None


class PublicationAcknowledgementListResponse(BaseModel):
    organization_id: str
    publication_id: str
    acknowledgements: list[PublicationAcknowledgementResponse]


class PublicationNotificationResponse(BaseModel):
    id: str
    publication_id: str
    employee_id: str
    notification_type: str
    channel: str
    status: str
    created_at: datetime


class EmployeePublicationLinkRequest(BaseModel):
    expires_in_hours: int = Field(default=168, ge=1, le=720)


class EmployeePublicationLinkResponse(BaseModel):
    organization_id: str
    publication_id: str
    schedule_run_id: str
    employee_id: str
    token: str
    expires_at: datetime
    employee_url: str


class EmployeePublicationContextResponse(BaseModel):
    organization_id: str
    publication_id: str
    schedule_run_id: str
    employee_id: str
    employee_name: str
    period_start: date
    period_end: date
    acknowledgement: PublicationAcknowledgementResponse
    notifications: list[PublicationNotificationResponse]


@router.post(
    "/{organization_id}/employee-user-links",
    response_model=EmployeeUserLinkResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_employee_user_link(
    organization_id: str,
    request: EmployeeUserLinkRequest,
    db_session: Session = Depends(get_db_session),
) -> EmployeeUserLinkResponse:
    require_roles(db_session, ADMIN_ROLES)
    _get_organization_or_404(organization_id, db_session)
    _get_employee_or_422(organization_id, request.employee_id, db_session)
    user = db_session.get(User, request.user_id)
    if user is None:
        raise HTTPException(status_code=422, detail="User not found")
    link = EmployeeUserLink(
        id=_new_id("employee_link"),
        organization_id=organization_id,
        employee_id=request.employee_id,
        user_id=request.user_id,
        status=request.status,
    )
    db_session.add(link)
    db_session.commit()
    return _employee_user_link_response(link)


@router.get(
    "/{organization_id}/employee-user-links",
    response_model=list[EmployeeUserLinkResponse],
)
def list_employee_user_links(
    organization_id: str,
    db_session: Session = Depends(get_db_session),
) -> list[EmployeeUserLinkResponse]:
    require_roles(db_session, ADMIN_ROLES)
    _get_organization_or_404(organization_id, db_session)
    links = db_session.execute(
        select(EmployeeUserLink)
        .where(EmployeeUserLink.organization_id == organization_id)
        .order_by(EmployeeUserLink.created_at, EmployeeUserLink.id)
    ).scalars()
    return [_employee_user_link_response(link) for link in links]


@router.post(
    "/{organization_id}/employee-requests",
    response_model=EmployeeRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_employee_request(
    organization_id: str,
    request: EmployeeRequestCreate,
    db_session: Session = Depends(get_db_session),
) -> EmployeeRequestResponse:
    _get_organization_or_404(organization_id, db_session)
    _get_employee_or_422(organization_id, request.employee_id, db_session)
    actor = current_actor(db_session)
    if actor.auth_required and actor.role == "employee":
        _require_employee_link(organization_id, request.employee_id, actor.user_id, db_session)
        requested_by_user_id = actor.user_id
    elif actor.auth_required:
        require_roles(db_session, ADMIN_ROLES)
        requested_by_user_id = request.requested_by_user_id
    else:
        requested_by_user_id = request.requested_by_user_id
    if requested_by_user_id is not None and db_session.get(User, requested_by_user_id) is None:
        raise HTTPException(status_code=422, detail="requested_by_user_id not found")
    now = utc_now()
    employee_request = EmployeeRequest(
        id=_new_id("employee_request"),
        organization_id=organization_id,
        employee_id=request.employee_id,
        requested_by_user_id=requested_by_user_id,
        type=request.type,
        status="pending",
        starts_at=request.starts_at,
        ends_at=request.ends_at,
        note=request.note,
        created_at=now,
    )
    db_session.add(employee_request)
    _add_audit(
        db_session,
        organization_id,
        action="employee_request_submitted",
        target_id=employee_request.id,
        metadata={"employee_id": request.employee_id, "type": request.type},
    )
    db_session.commit()
    return _employee_request_response(employee_request)


@router.get(
    "/{organization_id}/employee-requests",
    response_model=list[EmployeeRequestResponse],
)
def list_employee_requests(
    organization_id: str,
    status_filter: str | None = None,
    db_session: Session = Depends(get_db_session),
) -> list[EmployeeRequestResponse]:
    _get_organization_or_404(organization_id, db_session)
    actor = current_actor(db_session)
    query = select(EmployeeRequest).where(EmployeeRequest.organization_id == organization_id)
    if actor.auth_required and actor.role == "employee":
        employee_ids = _linked_employee_ids(organization_id, actor.user_id, db_session)
        query = query.where(EmployeeRequest.employee_id.in_(employee_ids))
    elif actor.auth_required:
        require_roles(db_session, ADMIN_ROLES)
    if status_filter:
        query = query.where(EmployeeRequest.status == status_filter)
    requests = db_session.execute(
        query.order_by(EmployeeRequest.created_at.desc(), EmployeeRequest.id)
    ).scalars()
    return [_employee_request_response(request) for request in requests]


@router.post(
    "/{organization_id}/employee-requests/{employee_request_id}/approve",
    response_model=EmployeeRequestResponse,
)
def approve_employee_request(
    organization_id: str,
    employee_request_id: str,
    request: EmployeeRequestReview,
    db_session: Session = Depends(get_db_session),
) -> EmployeeRequestResponse:
    actor = require_roles(db_session, ADMIN_ROLES)
    employee_request = _get_employee_request_or_404(
        organization_id,
        employee_request_id,
        db_session,
    )
    if employee_request.status != "pending":
        raise HTTPException(status_code=409, detail="EmployeeRequest is not pending")
    now = utc_now()
    employee_request.status = "approved"
    employee_request.manager_reason = request.reason
    employee_request.reviewed_by_user_id = (
        actor.user_id if actor.auth_required else request.reviewed_by_user_id
    )
    employee_request.reviewed_at = now
    if employee_request.type in {"vacation", "unavailable"}:
        unavailability = Unavailability(
            id=_new_id("unavailability"),
            organization_id=organization_id,
            employee_id=employee_request.employee_id,
            type="vacation" if employee_request.type == "vacation" else "personal",
            starts_at=employee_request.starts_at,
            ends_at=employee_request.ends_at,
            override_allowed=False,
            note=employee_request.note,
            created_at=now,
        )
        db_session.add(unavailability)
        db_session.flush()
        employee_request.source_unavailability_id = unavailability.id
    _add_audit(
        db_session,
        organization_id,
        action="employee_request_approved",
        target_id=employee_request.id,
        metadata={
            "employee_id": employee_request.employee_id,
            "source_unavailability_id": employee_request.source_unavailability_id,
        },
    )
    db_session.commit()
    return _employee_request_response(employee_request)


@router.post(
    "/{organization_id}/employee-requests/{employee_request_id}/reject",
    response_model=EmployeeRequestResponse,
)
def reject_employee_request(
    organization_id: str,
    employee_request_id: str,
    request: EmployeeRequestReview,
    db_session: Session = Depends(get_db_session),
) -> EmployeeRequestResponse:
    actor = require_roles(db_session, ADMIN_ROLES)
    employee_request = _get_employee_request_or_404(
        organization_id,
        employee_request_id,
        db_session,
    )
    if employee_request.status != "pending":
        raise HTTPException(status_code=409, detail="EmployeeRequest is not pending")
    employee_request.status = "rejected"
    employee_request.manager_reason = request.reason
    employee_request.reviewed_by_user_id = (
        actor.user_id if actor.auth_required else request.reviewed_by_user_id
    )
    employee_request.reviewed_at = utc_now()
    _add_audit(
        db_session,
        organization_id,
        action="employee_request_rejected",
        target_id=employee_request.id,
        metadata={"employee_id": employee_request.employee_id},
    )
    db_session.commit()
    return _employee_request_response(employee_request)


@router.post(
    "/{organization_id}/schedule-publications/{publication_id}/employee-links/{employee_id}",
    response_model=EmployeePublicationLinkResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_employee_publication_link(
    organization_id: str,
    publication_id: str,
    employee_id: str,
    request: EmployeePublicationLinkRequest,
    db_session: Session = Depends(get_db_session),
) -> EmployeePublicationLinkResponse:
    require_roles(db_session, ADMIN_ROLES)
    publication = _get_publication_or_404(organization_id, publication_id, db_session)
    _get_employee_or_422(organization_id, employee_id, db_session)
    secret = _employee_link_secret()
    now = utc_now()
    expires_at = now + timedelta(hours=request.expires_in_hours)
    token = sign_employee_deep_link(
        secret=secret,
        organization_id=organization_id,
        publication_id=publication_id,
        employee_id=employee_id,
        expires_at=expires_at,
        issued_at=now,
    )
    employee_url = _employee_publication_url(
        organization_id=organization_id,
        publication_id=publication_id,
        schedule_run_id=publication.schedule_run_id,
        employee_id=employee_id,
        token=token,
    )
    _add_audit(
        db_session,
        organization_id,
        action="employee_publication_link_created",
        target_id=publication_id,
        metadata={
            "employee_id": employee_id,
            "expires_at": expires_at.isoformat(),
        },
    )
    db_session.commit()
    return EmployeePublicationLinkResponse(
        organization_id=organization_id,
        publication_id=publication_id,
        schedule_run_id=publication.schedule_run_id,
        employee_id=employee_id,
        token=token,
        expires_at=expires_at,
        employee_url=employee_url,
    )


@public_router.get(
    "/schedule-publications/{publication_id}",
    response_model=EmployeePublicationContextResponse,
)
def get_employee_publication_context(
    publication_id: str,
    organization_id: str,
    employee_id: str,
    authorization: str | None = Header(default=None, alias="Authorization"),
    db_session: Session = Depends(get_db_session),
) -> EmployeePublicationContextResponse:
    publication, employee = _verify_employee_publication_link(
        organization_id=organization_id,
        publication_id=publication_id,
        employee_id=employee_id,
        token=_employee_link_token_from_authorization(authorization),
        db_session=db_session,
    )
    acknowledgement = _get_publication_acknowledgement_or_404(
        organization_id=organization_id,
        publication_id=publication_id,
        employee_id=employee_id,
        db_session=db_session,
    )
    notifications = _publication_notifications(
        organization_id=organization_id,
        publication_id=publication_id,
        employee_id=employee_id,
        db_session=db_session,
    )
    return EmployeePublicationContextResponse(
        organization_id=organization_id,
        publication_id=publication_id,
        schedule_run_id=publication.schedule_run_id,
        employee_id=employee_id,
        employee_name=employee.name,
        period_start=publication.period_start,
        period_end=publication.period_end,
        acknowledgement=_acknowledgement_response(acknowledgement),
        notifications=[
            _notification_response(notification)
            for notification in notifications
        ],
    )


@public_router.post(
    "/schedule-publications/{publication_id}/acknowledgement",
    response_model=PublicationAcknowledgementResponse,
)
def acknowledge_employee_publication_link(
    publication_id: str,
    organization_id: str,
    employee_id: str,
    request: AcknowledgementUpdateRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
    db_session: Session = Depends(get_db_session),
) -> PublicationAcknowledgementResponse:
    _verify_employee_publication_link(
        organization_id=organization_id,
        publication_id=publication_id,
        employee_id=employee_id,
        token=_employee_link_token_from_authorization(authorization),
        db_session=db_session,
    )
    acknowledgement = _get_publication_acknowledgement_or_404(
        organization_id=organization_id,
        publication_id=publication_id,
        employee_id=employee_id,
        db_session=db_session,
    )
    acknowledgement.status = request.status
    acknowledgement.acknowledged_at = utc_now()
    _add_audit(
        db_session,
        organization_id,
        action="publication_acknowledged",
        target_id=publication_id,
        metadata={"employee_id": employee_id, "access": "signed_employee_link"},
    )
    db_session.commit()
    return _acknowledgement_response(acknowledgement)


@router.get(
    "/{organization_id}/schedule-publications/{publication_id}/acknowledgements",
    response_model=PublicationAcknowledgementListResponse,
)
def list_publication_acknowledgements(
    organization_id: str,
    publication_id: str,
    db_session: Session = Depends(get_db_session),
) -> PublicationAcknowledgementListResponse:
    _get_publication_or_404(organization_id, publication_id, db_session)
    actor = current_actor(db_session)
    employee_ids: set[str] | None = None
    if actor.auth_required and actor.role == "employee":
        employee_ids = _linked_employee_ids(organization_id, actor.user_id, db_session)
    elif actor.auth_required:
        require_roles(db_session, ADMIN_ROLES)
    query = select(PublicationAcknowledgement).where(
        PublicationAcknowledgement.organization_id == organization_id,
        PublicationAcknowledgement.publication_id == publication_id,
    )
    if employee_ids is not None:
        query = query.where(PublicationAcknowledgement.employee_id.in_(employee_ids))
    acknowledgements = db_session.execute(
        query.order_by(PublicationAcknowledgement.employee_id)
    ).scalars()
    return PublicationAcknowledgementListResponse(
        organization_id=organization_id,
        publication_id=publication_id,
        acknowledgements=[
            _acknowledgement_response(acknowledgement)
            for acknowledgement in acknowledgements
        ],
    )


@router.post(
    "/{organization_id}/schedule-publications/{publication_id}/acknowledgements/{employee_id}",
    response_model=PublicationAcknowledgementResponse,
)
def acknowledge_publication(
    organization_id: str,
    publication_id: str,
    employee_id: str,
    request: AcknowledgementUpdateRequest,
    db_session: Session = Depends(get_db_session),
) -> PublicationAcknowledgementResponse:
    _get_publication_or_404(organization_id, publication_id, db_session)
    _get_employee_or_422(organization_id, employee_id, db_session)
    actor = current_actor(db_session)
    if actor.auth_required and actor.role == "employee":
        _require_employee_link(organization_id, employee_id, actor.user_id, db_session)
    elif actor.auth_required:
        require_roles(db_session, ADMIN_ROLES)
    acknowledgement = db_session.execute(
        select(PublicationAcknowledgement).where(
            PublicationAcknowledgement.organization_id == organization_id,
            PublicationAcknowledgement.publication_id == publication_id,
            PublicationAcknowledgement.employee_id == employee_id,
        )
    ).scalar_one_or_none()
    if acknowledgement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PublicationAcknowledgement not found",
        )
    acknowledgement.status = request.status
    acknowledgement.acknowledged_at = utc_now()
    _add_audit(
        db_session,
        organization_id,
        action="publication_acknowledged",
        target_id=publication_id,
        metadata={"employee_id": employee_id},
    )
    db_session.commit()
    return _acknowledgement_response(acknowledgement)


def _get_organization_or_404(
    organization_id: str,
    db_session: Session,
) -> Organization:
    organization = db_session.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return organization


def _get_employee_or_422(
    organization_id: str,
    employee_id: str,
    db_session: Session,
) -> Employee:
    employee = db_session.get(Employee, employee_id)
    if employee is None or employee.organization_id != organization_id:
        raise HTTPException(status_code=422, detail="Employee not found")
    return employee


def _employee_link_token_from_authorization(authorization: str | None) -> str:
    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "EMPLOYEE_LINK_TOKEN_REQUIRED",
                "message": "Authorization Bearer employee link token is required.",
                "field": "Authorization",
            },
        )
    scheme, separator, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not separator or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_EMPLOYEE_LINK_TOKEN",
                "message": "Authorization must be a Bearer employee link token.",
                "field": "Authorization",
                "reason": "MALFORMED_AUTHORIZATION",
            },
        )
    return token


def _verify_employee_publication_link(
    *,
    organization_id: str,
    publication_id: str,
    employee_id: str,
    token: str,
    db_session: Session,
) -> tuple[SchedulePublication, Employee]:
    try:
        verify_employee_deep_link(
            token,
            secret=_employee_link_secret(),
            organization_id=organization_id,
            publication_id=publication_id,
            employee_id=employee_id,
        )
    except EmployeeDeepLinkTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_EMPLOYEE_LINK_TOKEN",
                "message": "Signed employee publication link is invalid.",
                "field": "token",
                "reason": exc.code,
            },
        ) from exc
    set_tenant_context(db_session, organization_id)
    publication = _get_publication_or_404(organization_id, publication_id, db_session)
    if publication.status != "published":
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={
                "code": "PUBLICATION_NOT_AVAILABLE",
                "message": "SchedulePublication is not available through this link.",
                "field": "publication_id",
            },
        )
    employee = _get_employee_or_422(organization_id, employee_id, db_session)
    return publication, employee


def _get_publication_acknowledgement_or_404(
    *,
    organization_id: str,
    publication_id: str,
    employee_id: str,
    db_session: Session,
) -> PublicationAcknowledgement:
    acknowledgement = db_session.execute(
        select(PublicationAcknowledgement).where(
            PublicationAcknowledgement.organization_id == organization_id,
            PublicationAcknowledgement.publication_id == publication_id,
            PublicationAcknowledgement.employee_id == employee_id,
        )
    ).scalar_one_or_none()
    if acknowledgement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PublicationAcknowledgement not found",
        )
    return acknowledgement


def _publication_notifications(
    *,
    organization_id: str,
    publication_id: str,
    employee_id: str,
    db_session: Session,
) -> list[PublicationNotification]:
    return list(
        db_session.execute(
            select(PublicationNotification)
            .where(
                PublicationNotification.organization_id == organization_id,
                PublicationNotification.publication_id == publication_id,
                PublicationNotification.employee_id == employee_id,
            )
            .order_by(PublicationNotification.created_at, PublicationNotification.id)
        ).scalars()
    )


def _get_employee_request_or_404(
    organization_id: str,
    employee_request_id: str,
    db_session: Session,
) -> EmployeeRequest:
    employee_request = db_session.get(EmployeeRequest, employee_request_id)
    if employee_request is None or employee_request.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="EmployeeRequest not found")
    return employee_request


def _get_publication_or_404(
    organization_id: str,
    publication_id: str,
    db_session: Session,
) -> SchedulePublication:
    publication = db_session.get(SchedulePublication, publication_id)
    if publication is None or publication.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="SchedulePublication not found")
    return publication


def _linked_employee_ids(
    organization_id: str,
    user_id: str | None,
    db_session: Session,
) -> set[str]:
    if user_id is None:
        return set()
    rows = db_session.execute(
        select(EmployeeUserLink.employee_id).where(
            EmployeeUserLink.organization_id == organization_id,
            EmployeeUserLink.user_id == user_id,
            EmployeeUserLink.status == "linked",
        )
    ).scalars()
    return set(rows)


def _require_employee_link(
    organization_id: str,
    employee_id: str,
    user_id: str | None,
    db_session: Session,
) -> None:
    if employee_id not in _linked_employee_ids(organization_id, user_id, db_session):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "EMPLOYEE_LINK_REQUIRED",
                "message": "Employee self-service access requires a linked employee.",
                "field": "employee_id",
            },
        )


def _employee_user_link_response(link: EmployeeUserLink) -> EmployeeUserLinkResponse:
    return EmployeeUserLinkResponse(
        id=link.id,
        organization_id=link.organization_id,
        employee_id=link.employee_id,
        user_id=link.user_id,
        status=link.status,
    )


def _employee_request_response(
    employee_request: EmployeeRequest,
) -> EmployeeRequestResponse:
    return EmployeeRequestResponse(
        id=employee_request.id,
        organization_id=employee_request.organization_id,
        employee_id=employee_request.employee_id,
        requested_by_user_id=employee_request.requested_by_user_id,
        type=employee_request.type,
        status=employee_request.status,
        starts_at=employee_request.starts_at,
        ends_at=employee_request.ends_at,
        note=employee_request.note,
        manager_reason=employee_request.manager_reason,
        reviewed_by_user_id=employee_request.reviewed_by_user_id,
        reviewed_at=employee_request.reviewed_at,
        source_unavailability_id=employee_request.source_unavailability_id,
        created_at=employee_request.created_at,
    )


def _acknowledgement_response(
    acknowledgement: PublicationAcknowledgement,
) -> PublicationAcknowledgementResponse:
    return PublicationAcknowledgementResponse(
        id=acknowledgement.id,
        publication_id=acknowledgement.publication_id,
        employee_id=acknowledgement.employee_id,
        status=acknowledgement.status,
        acknowledged_at=acknowledgement.acknowledged_at,
    )


def _notification_response(
    notification: PublicationNotification,
) -> PublicationNotificationResponse:
    return PublicationNotificationResponse(
        id=notification.id,
        publication_id=notification.publication_id,
        employee_id=notification.employee_id,
        notification_type=notification.notification_type,
        channel=notification.channel,
        status=notification.status,
        created_at=notification.created_at,
    )


def _employee_link_secret() -> str:
    secret = os.environ.get("WORKSCHEDULEAI_EMPLOYEE_LINK_SECRET")
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "EMPLOYEE_LINK_SECRET_REQUIRED",
                "message": (
                    "Signed employee links require "
                    "WORKSCHEDULEAI_EMPLOYEE_LINK_SECRET."
                ),
                "field": "WORKSCHEDULEAI_EMPLOYEE_LINK_SECRET",
            },
        )
    return secret


def _employee_publication_url(
    *,
    organization_id: str,
    publication_id: str,
    schedule_run_id: str,
    employee_id: str,
    token: str,
) -> str:
    query = urlencode(
        {
            "organizationId": organization_id,
            "publicationId": publication_id,
            "runId": schedule_run_id,
            "employeeId": employee_id,
        }
    )
    fragment = urlencode({"token": token})
    return f"/employee?{query}#{fragment}"


def _add_audit(
    db_session: Session,
    organization_id: str,
    *,
    action: str,
    target_id: str,
    metadata: dict[str, object],
) -> None:
    actor = current_actor(db_session)
    db_session.add(
        AuditLog(
            id=_new_id("audit"),
            organization_id=organization_id,
            actor_user_id=actor.user_id,
            action=action,
            target_type="employee_workflow",
            target_id=target_id,
            metadata_json=json.dumps(metadata, ensure_ascii=False, sort_keys=True),
        )
    )


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"
