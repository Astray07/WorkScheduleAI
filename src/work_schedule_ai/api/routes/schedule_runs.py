from __future__ import annotations

from io import BytesIO
from datetime import date, datetime, timedelta
import hashlib
import json
from typing import Literal
from uuid import uuid4
import zipfile
from xml.sax.saxutils import escape as xml_escape

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import delete, select
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import Session

from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.db.models import (
    AuditLog,
    Assignment as AssignmentRecord,
    Employee,
    EmployeeRole,
    Organization,
    OverrideApproval,
    PairConstraint,
    RelaxationProposal as RelaxationProposalRecord,
    Role,
    ScheduleIssue as ScheduleIssueRecord,
    ScheduleRecalculationRequest,
    ScheduleInputSnapshot,
    SchedulePublication,
    ScheduleRequirement as ScheduleRequirementRecord,
    ScheduleRun,
    ShiftSlot as ShiftSlotRecord,
    SolverDiagnosticEvent as SolverDiagnosticEventRecord,
    ShiftRequirement,
    ShiftType,
    Unavailability,
    utc_now,
)
from work_schedule_ai.llm.explanations import fallback_explanation
from work_schedule_ai.solver.models import (
    BlockedPair,
    EmployeeInput,
    ScheduleRequirementInput,
    ScheduleSlotInput,
    SolveScheduleRequest,
)
from work_schedule_ai.solver.ortools_solver import solve_schedule
from work_schedule_ai.worker.schedule_worker import (
    cancel_schedule_run as worker_cancel_schedule_run,
)
from work_schedule_ai.worker.queue import enqueue_schedule_run


router = APIRouter(prefix="/organizations", tags=["schedule-runs"])

class ScheduleRunCreateRequest(BaseModel):
    period_start: date
    period_end: date
    template: Literal[
        "one_shift_per_day",
        "morning_afternoon_night",
        "on_call",
        "custom",
    ] = "one_shift_per_day"
    deterministic_mode: bool = True
    timeout_seconds: int = Field(default=30, ge=1, le=120)

    @model_validator(mode="after")
    def validate_period_length(self):
        day_count = (self.period_end - self.period_start).days + 1
        if day_count < 1:
            raise ValueError("period_end must be on or after period_start")
        if day_count > 31:
            raise ValueError("ScheduleRun period cannot exceed 31 days")
        return self


class ApproveRelaxationProposalRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
    notification_required: bool


class OverrideApprovalResponse(BaseModel):
    id: str
    schedule_run_id: str
    relaxation_proposal_id: str
    type: str
    notification_required: bool
    created_at: datetime


class RecalculateScheduleRunRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class PublishScheduleRunRequest(BaseModel):
    expected_assignment_snapshot_hash: str = Field(min_length=1)
    expected_issue_snapshot_hash: str = Field(min_length=1)


class ManualEditValidationRequest(BaseModel):
    slot_id: str = Field(min_length=1)
    role_id: str = Field(min_length=1)
    employee_id: str = Field(min_length=1)
    locked_by_user: bool


class FieldErrorResponse(BaseModel):
    field: str
    code: str
    message: str


class ManualEditValidationResponse(BaseModel):
    valid: bool
    blocking_errors: list[FieldErrorResponse]
    warnings: list[FieldErrorResponse]


class ScheduleRunProgress(BaseModel):
    phase: str
    message: str
    started_at: datetime | None
    timeout_seconds: int


class ScoreSummary(BaseModel):
    hard: int
    approvable: int
    soft: int
    severity_label: str


class LLMExplanation(BaseModel):
    status: str
    text: str | None
    source: str


class ImpactPreview(BaseModel):
    resolved_issue_ids: list[str]
    new_warning_count: int
    unavailable_reasons: list[str] = Field(default_factory=list)


class ScheduleIssueResponse(BaseModel):
    id: str
    slot_id: str | None
    role_id: str | None
    type: str
    missing_count: int
    severity: str
    reason_code: str
    display_message: str
    attempt_no: int
    related_proposal_ids: list[str] = Field(default_factory=list)


class RelaxationProposalResponse(BaseModel):
    id: str
    group_id: str | None
    requires_proposal_ids: list[str]
    type: str
    severity: str
    affected_slot_id: str | None
    display_summary: str
    impact_preview: ImpactPreview
    status: str
    attempt_no: int
    llm_explanation: LLMExplanation


class ScheduleRunResponse(BaseModel):
    id: str
    organization_id: str
    period_start: date
    period_end: date
    status: str
    solver_status: str | None
    solution_quality: str
    current_attempt_no: int
    recalculation_count: int
    input_snapshot_hash: str | None
    progress: ScheduleRunProgress
    score_summary: ScoreSummary
    issues: list[ScheduleIssueResponse]
    proposals: list[RelaxationProposalResponse]
    llm_explanation: LLMExplanation
    updated_at: datetime


class ShiftSlotResponse(BaseModel):
    id: str
    local_date: date
    label: str
    starts_at: str
    ends_at: str


class ShiftRequirementResponse(BaseModel):
    id: str
    slot_id: str
    role_id: str
    role_name: str
    required_count: int


class AssignmentResponse(BaseModel):
    id: str
    slot_id: str
    role_id: str
    employee_id: str
    employee_name: str
    source: str
    locked_by_user: bool
    warning_state: str
    warning_message: str | None = None
    attempt_no: int


class SchedulePublicationResponse(BaseModel):
    id: str
    organization_id: str
    schedule_run_id: str
    period_start: date
    period_end: date
    status: str
    assignment_snapshot_hash: str
    issue_snapshot_hash: str
    published_at: datetime


class ScheduleRunResultResponse(BaseModel):
    schedule_run_id: str
    status: str
    solution_quality: str
    current_attempt_no: int
    recalculation_count: int
    read_only: bool
    publication: SchedulePublicationResponse | None
    assignment_snapshot_hash: str
    issue_snapshot_hash: str
    slots: list[ShiftSlotResponse]
    requirements: list[ShiftRequirementResponse]
    assignments: list[AssignmentResponse]
    issues: list[ScheduleIssueResponse]
    proposals: list[RelaxationProposalResponse]
    score_summary: ScoreSummary
    llm_explanation: LLMExplanation


@router.post(
    "/{organization_id}/schedule-runs",
    response_model=ScheduleRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_schedule_run(
    organization_id: str,
    request: ScheduleRunCreateRequest,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
    ),
    db_session: Session = Depends(get_db_session),
) -> ScheduleRunResponse:
    organization = db_session.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    snapshot_payload = _build_snapshot_payload(
        organization_id=organization_id,
        request=request,
        db_session=db_session,
    )
    snapshot_hash = _snapshot_hash(snapshot_payload)

    if idempotency_key is not None:
        existing_run = db_session.execute(
            select(ScheduleRun).where(
                ScheduleRun.organization_id == organization_id,
                ScheduleRun.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if existing_run is not None:
            if existing_run.input_snapshot_hash != snapshot_hash:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "SCHEDULE_RUN_IDEMPOTENCY_CONFLICT",
                        "message": (
                            "Idempotency-Key was reused with different "
                            "ScheduleRun input."
                        ),
                        "field": "Idempotency-Key",
                    },
                )
            return _schedule_run_response(existing_run, db_session)

    run_id = _new_id("run")
    now = utc_now()
    run = ScheduleRun(
        id=run_id,
        organization_id=organization_id,
        period_start=request.period_start,
        period_end=request.period_end,
        template=request.template,
        deterministic_mode=request.deterministic_mode,
        timeout_seconds=request.timeout_seconds,
        status="queued",
        solver_status=None,
        solution_quality="unknown",
        current_attempt_no=1,
        recalculation_count=0,
        input_snapshot_hash=snapshot_hash,
        idempotency_key=idempotency_key,
        created_at=now,
        updated_at=now,
        started_at=None,
        finished_at=None,
    )
    snapshot = ScheduleInputSnapshot(
        id=_new_id("snapshot"),
        organization_id=organization_id,
        schedule_run_id=run_id,
        snapshot_hash=snapshot_hash,
        payload_json=json.dumps(snapshot_payload, ensure_ascii=False, sort_keys=True),
    )
    db_session.add(run)
    db_session.flush()
    db_session.add(snapshot)
    db_session.flush()
    db_session.commit()
    enqueue_schedule_run(run.id)

    return _schedule_run_response(run, db_session)


@router.get(
    "/{organization_id}/schedule-runs/{schedule_run_id}",
    response_model=ScheduleRunResponse,
)
def get_schedule_run(
    organization_id: str,
    schedule_run_id: str,
    db_session: Session = Depends(get_db_session),
) -> ScheduleRunResponse:
    run = _get_schedule_run_or_404(organization_id, schedule_run_id, db_session)
    return _schedule_run_response(run, db_session)


@router.get(
    "/{organization_id}/schedule-runs/{schedule_run_id}/result",
    response_model=ScheduleRunResultResponse,
)
def get_schedule_run_result(
    organization_id: str,
    schedule_run_id: str,
    db_session: Session = Depends(get_db_session),
) -> ScheduleRunResultResponse:
    run = _get_schedule_run_or_404(organization_id, schedule_run_id, db_session)
    publication = _get_publication_for_run(run, db_session)
    artifacts = (
        _artifacts_from_publication_snapshot(publication)
        if publication is not None and publication.result_snapshot_json
        else _result_artifacts_for_run(run, db_session)
    )
    hashes = _artifact_hashes(artifacts)
    return ScheduleRunResultResponse(
        schedule_run_id=run.id,
        status=run.status,
        solution_quality=run.solution_quality,
        current_attempt_no=run.current_attempt_no,
        recalculation_count=run.recalculation_count,
        read_only=publication is not None and publication.status == "published",
        publication=(
            _schedule_publication_response(publication)
            if publication is not None
            else None
        ),
        assignment_snapshot_hash=hashes.assignment_snapshot_hash,
        issue_snapshot_hash=hashes.issue_snapshot_hash,
        slots=artifacts.slots,
        requirements=artifacts.requirements,
        assignments=artifacts.assignments,
        issues=artifacts.issues,
        proposals=artifacts.proposals,
        score_summary=artifacts.score_summary,
        llm_explanation=_llm_explanation(),
    )


@router.post(
    "/{organization_id}/schedule-runs/{schedule_run_id}/manual-edits/validate",
    response_model=ManualEditValidationResponse,
)
def validate_manual_edit(
    organization_id: str,
    schedule_run_id: str,
    request: ManualEditValidationRequest,
    db_session: Session = Depends(get_db_session),
) -> ManualEditValidationResponse:
    run = _get_schedule_run_or_404(organization_id, schedule_run_id, db_session)
    publication = _get_publication_for_run(run, db_session)
    if publication is not None and publication.status == "published":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "SCHEDULE_RUN_ALREADY_PUBLISHED",
                "message": "Published ScheduleRun results are read-only.",
                "field": "schedule_run_id",
            },
        )

    artifacts = _result_artifacts_for_run(run, db_session)
    return _validate_manual_edit_request(
        organization_id=organization_id,
        request=request,
        artifacts=artifacts,
        db_session=db_session,
    )


@router.post(
    "/{organization_id}/schedule-runs/{schedule_run_id}/manual-edits",
    response_model=AssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def save_manual_edit(
    organization_id: str,
    schedule_run_id: str,
    request: ManualEditValidationRequest,
    db_session: Session = Depends(get_db_session),
) -> AssignmentResponse:
    run = _get_schedule_run_or_404(organization_id, schedule_run_id, db_session)
    publication = _get_publication_for_run(run, db_session)
    if publication is not None and publication.status == "published":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "SCHEDULE_RUN_ALREADY_PUBLISHED",
                "message": "Published ScheduleRun results are read-only.",
                "field": "schedule_run_id",
            },
        )

    artifacts = _result_artifacts_for_run(run, db_session)
    validation = _validate_manual_edit_request(
        organization_id=organization_id,
        request=request,
        artifacts=artifacts,
        db_session=db_session,
    )
    if not validation.valid:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "MANUAL_EDIT_INVALID",
                "message": "Manual edit has blocking validation errors.",
                "blocking_errors": [
                    error.model_dump(mode="json")
                    for error in validation.blocking_errors
                ],
            },
        )

    employee = db_session.get(Employee, request.employee_id)
    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        )

    stored_slot_id = _stored_artifact_id(run.id, request.slot_id)
    assignment_id = _stored_artifact_id(
        run.id,
        f"assign_manual_{request.slot_id}_{request.role_id}",
    )
    db_session.execute(
        delete(AssignmentRecord).where(
            AssignmentRecord.organization_id == organization_id,
            AssignmentRecord.schedule_run_id == run.id,
            AssignmentRecord.shift_slot_id == stored_slot_id,
            AssignmentRecord.role_id == request.role_id,
        )
    )
    warning_codes = [warning.code for warning in validation.warnings]
    assignment = AssignmentRecord(
        id=assignment_id,
        organization_id=organization_id,
        schedule_run_id=run.id,
        shift_slot_id=stored_slot_id,
        role_id=request.role_id,
        employee_id=request.employee_id,
        employee_name=employee.name,
        source="manual",
        locked_by_user=request.locked_by_user,
        warning_state="manual_warning" if warning_codes else "none",
        warning_message=(
            "Manual assignment saved with validation warnings."
            if warning_codes
            else None
        ),
        attempt_no=run.current_attempt_no,
    )
    db_session.add(assignment)
    _remove_resolved_manual_edit_issues(
        organization_id=organization_id,
        run=run,
        stored_slot_id=stored_slot_id,
        role_id=request.role_id,
        db_session=db_session,
    )
    db_session.add(
        AuditLog(
            id=_new_id("audit"),
            organization_id=organization_id,
            actor_user_id=None,
            action="manual_assignment_saved",
            target_type="assignment",
            target_id=_external_artifact_id(run.id, assignment_id),
            metadata_json=json.dumps(
                {
                    "schedule_run_id": run.id,
                    "slot_id": request.slot_id,
                    "role_id": request.role_id,
                    "employee_id": request.employee_id,
                    "locked_by_user": request.locked_by_user,
                    "warning_codes": warning_codes,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            created_at=utc_now(),
        )
    )
    run.updated_at = utc_now()
    db_session.commit()
    return _assignment_response_from_record(run, assignment)


@router.post(
    "/{organization_id}/schedule-runs/{schedule_run_id}/cancel",
    response_model=ScheduleRunResponse,
)
def cancel_schedule_run(
    organization_id: str,
    schedule_run_id: str,
    db_session: Session = Depends(get_db_session),
) -> ScheduleRunResponse:
    _get_schedule_run_or_404(organization_id, schedule_run_id, db_session)
    try:
        run = worker_cancel_schedule_run(db_session, schedule_run_id)
    except InvalidRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "SCHEDULE_RUN_NOT_CANCELABLE",
                "message": str(exc),
                "field": "status",
            },
        ) from exc
    return _schedule_run_response(run, db_session)


@router.post(
    "/{organization_id}/schedule-runs/{schedule_run_id}/relaxation-proposals/{proposal_id}/approve",
    response_model=OverrideApprovalResponse,
    status_code=status.HTTP_201_CREATED,
)
def approve_relaxation_proposal(
    organization_id: str,
    schedule_run_id: str,
    proposal_id: str,
    request: ApproveRelaxationProposalRequest,
    db_session: Session = Depends(get_db_session),
) -> OverrideApprovalResponse:
    run = _get_schedule_run_or_404(organization_id, schedule_run_id, db_session)
    artifacts = _result_artifacts_for_run(run, db_session)
    proposal = next(
        (candidate for candidate in artifacts.proposals if candidate.id == proposal_id),
        None,
    )
    if proposal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="RelaxationProposal not found",
        )

    existing_approval = db_session.execute(
        select(OverrideApproval).where(
            OverrideApproval.organization_id == organization_id,
            OverrideApproval.schedule_run_id == schedule_run_id,
            OverrideApproval.relaxation_proposal_id == proposal_id,
        )
    ).scalar_one_or_none()
    if existing_approval is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "RELAXATION_PROPOSAL_ALREADY_APPROVED",
                "message": "Relaxation proposal is already approved.",
                "field": "proposal_id",
            },
        )

    approval = OverrideApproval(
        id=_new_id("override"),
        organization_id=organization_id,
        schedule_run_id=schedule_run_id,
        relaxation_proposal_id=proposal_id,
        type=proposal.type,
        notification_required=request.notification_required,
        reason=request.reason,
        created_at=utc_now(),
    )
    db_session.add(approval)
    persisted_proposal = db_session.get(
        RelaxationProposalRecord,
        _stored_artifact_id(run.id, proposal.id),
    )
    if persisted_proposal is not None:
        persisted_proposal.status = "approved"
    db_session.commit()

    return OverrideApprovalResponse(
        id=approval.id,
        schedule_run_id=approval.schedule_run_id,
        relaxation_proposal_id=approval.relaxation_proposal_id,
        type=approval.type,
        notification_required=approval.notification_required,
        created_at=approval.created_at,
    )


@router.post(
    "/{organization_id}/schedule-runs/{schedule_run_id}/recalculate",
    response_model=ScheduleRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def recalculate_schedule_run(
    organization_id: str,
    schedule_run_id: str,
    request: RecalculateScheduleRunRequest,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
    ),
    db_session: Session = Depends(get_db_session),
) -> ScheduleRunResponse:
    run = _get_schedule_run_or_404(organization_id, schedule_run_id, db_session)

    publication = _get_publication_for_run(run, db_session)
    if publication is not None and publication.status == "published":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "SCHEDULE_RUN_ALREADY_PUBLISHED",
                "message": "Published ScheduleRun results are read-only.",
                "field": "schedule_run_id",
            },
        )

    if idempotency_key is not None:
        existing_request = db_session.execute(
            select(ScheduleRecalculationRequest).where(
                ScheduleRecalculationRequest.organization_id == organization_id,
                ScheduleRecalculationRequest.schedule_run_id == schedule_run_id,
                ScheduleRecalculationRequest.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if existing_request is not None:
            return _schedule_run_response(run, db_session)

    if run.status in {"queued", "running"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "SCHEDULE_RUN_NOT_READY",
                "message": "ScheduleRun must finish before it can be recalculated again.",
                "field": "schedule_run_id",
            },
        )

    approved_override_count = db_session.execute(
        select(OverrideApproval.id).where(
            OverrideApproval.organization_id == organization_id,
            OverrideApproval.schedule_run_id == schedule_run_id,
        )
    ).first()
    if approved_override_count is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "NO_APPROVED_OVERRIDE",
                "message": "At least one approved override is required to recalculate.",
                "field": "schedule_run_id",
            },
        )

    if run.recalculation_count >= 3:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "RECALCULATION_LIMIT_EXCEEDED",
                "message": "recalculation_count cannot exceed 3.",
                "field": "recalculation_count",
            },
        )

    run.recalculation_count += 1
    now = utc_now()
    run.updated_at = now
    run.status = "queued"
    run.solver_status = None
    run.solution_quality = "unknown"
    run.started_at = None
    run.finished_at = None
    recalculation_request = ScheduleRecalculationRequest(
        id=_new_id("recalc"),
        organization_id=organization_id,
        schedule_run_id=schedule_run_id,
        idempotency_key=idempotency_key,
        reason=request.reason,
        recalculation_count=run.recalculation_count,
    )
    db_session.add(recalculation_request)
    db_session.commit()
    enqueue_schedule_run(run.id)

    return _schedule_run_response(run, db_session)


@router.post(
    "/{organization_id}/schedule-runs/{schedule_run_id}/publications",
    response_model=SchedulePublicationResponse,
    status_code=status.HTTP_201_CREATED,
)
def publish_schedule_run(
    organization_id: str,
    schedule_run_id: str,
    request: PublishScheduleRunRequest,
    db_session: Session = Depends(get_db_session),
) -> SchedulePublicationResponse:
    run = _get_schedule_run_or_404(organization_id, schedule_run_id, db_session)
    artifacts = _result_artifacts_for_run(run, db_session)
    hashes = _artifact_hashes(artifacts)

    if (
        request.expected_assignment_snapshot_hash
        != hashes.assignment_snapshot_hash
        or request.expected_issue_snapshot_hash != hashes.issue_snapshot_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "SCHEDULE_RESULT_STALE",
                "message": "Schedule result snapshot hash does not match.",
                "field": "expected_assignment_snapshot_hash",
            },
        )

    if artifacts.issues:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "SCHEDULE_RESULT_HAS_ISSUES",
                "message": "ScheduleRun must have no open issues before publication.",
                "field": "schedule_run_id",
            },
        )

    existing_publication = _get_publication_for_run(run, db_session)
    if existing_publication is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "SCHEDULE_RUN_ALREADY_PUBLISHED",
                "message": "ScheduleRun already has a publication.",
                "field": "schedule_run_id",
            },
        )

    overlapping_publication = db_session.execute(
        select(SchedulePublication).where(
            SchedulePublication.organization_id == organization_id,
            SchedulePublication.status == "published",
            SchedulePublication.period_start < run.period_end,
            SchedulePublication.period_end > run.period_start,
        )
    ).scalar_one_or_none()
    if overlapping_publication is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "PUBLICATION_PERIOD_OVERLAP",
                "message": "Published SchedulePublication period overlaps.",
                "field": "period_start",
            },
        )

    now = utc_now()
    publication = SchedulePublication(
        id=_new_id("publication"),
        organization_id=organization_id,
        schedule_run_id=schedule_run_id,
        period_start=run.period_start,
        period_end=run.period_end,
        status="published",
        assignment_snapshot_hash=hashes.assignment_snapshot_hash,
        issue_snapshot_hash=hashes.issue_snapshot_hash,
        result_snapshot_json=json.dumps(
            _result_snapshot_payload(artifacts),
            ensure_ascii=False,
            sort_keys=True,
        ),
        published_at=now,
        created_at=now,
    )
    db_session.add(publication)
    db_session.commit()

    return _schedule_publication_response(publication)


@router.get("/{organization_id}/schedule-publications/{publication_id}/excel")
def download_schedule_publication_excel(
    organization_id: str,
    publication_id: str,
    db_session: Session = Depends(get_db_session),
) -> Response:
    publication = db_session.execute(
        select(SchedulePublication).where(
            SchedulePublication.organization_id == organization_id,
            SchedulePublication.id == publication_id,
        )
    ).scalar_one_or_none()
    if publication is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SchedulePublication not found",
        )

    run = db_session.get(ScheduleRun, publication.schedule_run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ScheduleRun not found",
        )

    artifacts = (
        _artifacts_from_publication_snapshot(publication)
        if publication.result_snapshot_json
        else _result_artifacts_for_run(run, db_session)
    )
    workbook = _build_schedule_workbook(publication, artifacts)
    filename = f"work_schedule_{publication.period_start}_{publication.period_end}.xlsx"
    return Response(
        content=workbook,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class _MockArtifacts(BaseModel):
    slots: list[ShiftSlotResponse]
    requirements: list[ShiftRequirementResponse]
    assignments: list[AssignmentResponse]
    issues: list[ScheduleIssueResponse]
    proposals: list[RelaxationProposalResponse]
    score_summary: ScoreSummary


class _ArtifactHashes(BaseModel):
    assignment_snapshot_hash: str
    issue_snapshot_hash: str


def _get_schedule_run_or_404(
    organization_id: str,
    schedule_run_id: str,
    db_session: Session,
) -> ScheduleRun:
    run = db_session.execute(
        select(ScheduleRun).where(
            ScheduleRun.organization_id == organization_id,
            ScheduleRun.id == schedule_run_id,
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ScheduleRun not found",
        )
    return run


def _get_publication_for_run(
    run: ScheduleRun,
    db_session: Session,
) -> SchedulePublication | None:
    return db_session.execute(
        select(SchedulePublication).where(
            SchedulePublication.organization_id == run.organization_id,
            SchedulePublication.schedule_run_id == run.id,
        )
    ).scalar_one_or_none()


def _schedule_publication_response(
    publication: SchedulePublication,
) -> SchedulePublicationResponse:
    return SchedulePublicationResponse(
        id=publication.id,
        organization_id=publication.organization_id,
        schedule_run_id=publication.schedule_run_id,
        period_start=publication.period_start,
        period_end=publication.period_end,
        status=publication.status,
        assignment_snapshot_hash=publication.assignment_snapshot_hash,
        issue_snapshot_hash=publication.issue_snapshot_hash,
        published_at=publication.published_at,
    )


def _schedule_run_response(
    run: ScheduleRun,
    db_session: Session,
) -> ScheduleRunResponse:
    artifacts = _result_artifacts_for_run(run, db_session)
    return ScheduleRunResponse(
        id=run.id,
        organization_id=run.organization_id,
        period_start=run.period_start,
        period_end=run.period_end,
        status=run.status,
        solver_status=run.solver_status,
        solution_quality=run.solution_quality,
        current_attempt_no=run.current_attempt_no,
        recalculation_count=run.recalculation_count,
        input_snapshot_hash=run.input_snapshot_hash,
        progress=_schedule_run_progress(run),
        score_summary=artifacts.score_summary,
        issues=artifacts.issues,
        proposals=artifacts.proposals,
        llm_explanation=_llm_explanation(),
        updated_at=run.updated_at,
    )


def _execute_schedule_run_artifacts(
    db_session: Session,
    run: ScheduleRun,
) -> None:
    artifacts = _mock_result_artifacts(run, db_session)
    _replace_persisted_artifacts(run, artifacts, db_session)


def _result_artifacts_for_run(
    run: ScheduleRun,
    db_session: Session,
) -> _MockArtifacts:
    if run.status in {"queued", "running"}:
        return _empty_result_artifacts()
    stored = _load_persisted_artifacts(run, db_session)
    if stored is not None:
        return stored
    return _mock_result_artifacts(run, db_session)


def _assignment_response_from_record(
    run: ScheduleRun,
    assignment: AssignmentRecord,
) -> AssignmentResponse:
    return AssignmentResponse(
        id=_external_artifact_id(run.id, assignment.id),
        slot_id=_external_artifact_id(run.id, assignment.shift_slot_id),
        role_id=assignment.role_id,
        employee_id=assignment.employee_id,
        employee_name=assignment.employee_name,
        source=assignment.source,
        locked_by_user=assignment.locked_by_user,
        warning_state=assignment.warning_state,
        warning_message=assignment.warning_message,
        attempt_no=assignment.attempt_no,
    )


def _remove_resolved_manual_edit_issues(
    *,
    organization_id: str,
    run: ScheduleRun,
    stored_slot_id: str,
    role_id: str,
    db_session: Session,
) -> None:
    db_session.execute(
        delete(ScheduleIssueRecord).where(
            ScheduleIssueRecord.organization_id == organization_id,
            ScheduleIssueRecord.schedule_run_id == run.id,
            ScheduleIssueRecord.shift_slot_id == stored_slot_id,
            ScheduleIssueRecord.role_id == role_id,
            ScheduleIssueRecord.type == "unfilled_requirement",
        )
    )
    db_session.execute(
        delete(RelaxationProposalRecord).where(
            RelaxationProposalRecord.organization_id == organization_id,
            RelaxationProposalRecord.schedule_run_id == run.id,
            RelaxationProposalRecord.affected_shift_slot_id == stored_slot_id,
        )
    )


def _schedule_run_progress(run: ScheduleRun) -> ScheduleRunProgress:
    if run.status == "queued":
        return ScheduleRunProgress(
            phase="queued",
            message="ScheduleRun is queued for worker processing.",
            started_at=run.started_at,
            timeout_seconds=run.timeout_seconds,
        )
    if run.status == "running":
        return ScheduleRunProgress(
            phase="running",
            message="ScheduleRun is being processed by the worker.",
            started_at=run.started_at,
            timeout_seconds=run.timeout_seconds,
        )
    if run.status == "canceled":
        return ScheduleRunProgress(
            phase="canceled",
            message="ScheduleRun was canceled.",
            started_at=run.started_at,
            timeout_seconds=run.timeout_seconds,
        )
    if run.status == "failed":
        return ScheduleRunProgress(
            phase="failed",
            message="ScheduleRun failed during worker processing.",
            started_at=run.started_at,
            timeout_seconds=run.timeout_seconds,
        )
    return ScheduleRunProgress(
        phase="completed",
        message="Schedule result is ready.",
        started_at=run.started_at,
        timeout_seconds=run.timeout_seconds,
    )


def _empty_result_artifacts() -> _MockArtifacts:
    return _MockArtifacts(
        slots=[],
        requirements=[],
        assignments=[],
        issues=[],
        proposals=[],
        score_summary=ScoreSummary(
            hard=0,
            approvable=0,
            soft=0,
            severity_label="none",
        ),
    )


def _replace_persisted_artifacts(
    run: ScheduleRun,
    artifacts: _MockArtifacts,
    db_session: Session,
) -> None:
    artifacts = _merge_locked_manual_assignments(
        run=run,
        artifacts=artifacts,
        db_session=db_session,
    )
    for model in (
        RelaxationProposalRecord,
        SolverDiagnosticEventRecord,
        ScheduleIssueRecord,
        AssignmentRecord,
        ScheduleRequirementRecord,
        ShiftSlotRecord,
    ):
        db_session.execute(
            delete(model).where(
                model.organization_id == run.organization_id,
                model.schedule_run_id == run.id,
            )
        )
    db_session.flush()

    db_session.add_all(
        [
            ShiftSlotRecord(
                id=_stored_artifact_id(run.id, slot.id),
                organization_id=run.organization_id,
                schedule_run_id=run.id,
                shift_type_id=_shift_type_id_from_slot_id(slot.id),
                local_date=slot.local_date,
                label=slot.label,
                starts_at=slot.starts_at,
                ends_at=slot.ends_at,
                timezone="Asia/Seoul",
                status="generated",
                attempt_no=run.current_attempt_no,
            )
            for slot in artifacts.slots
        ]
    )
    db_session.flush()
    db_session.add_all(
        [
            ScheduleRequirementRecord(
                id=_stored_artifact_id(run.id, requirement.id),
                organization_id=run.organization_id,
                schedule_run_id=run.id,
                shift_slot_id=_stored_artifact_id(run.id, requirement.slot_id),
                role_id=requirement.role_id,
                role_name=requirement.role_name,
                required_count=requirement.required_count,
                attempt_no=run.current_attempt_no,
            )
            for requirement in artifacts.requirements
        ]
    )
    db_session.add_all(
        [
            AssignmentRecord(
                id=_stored_artifact_id(run.id, assignment.id),
                organization_id=run.organization_id,
                schedule_run_id=run.id,
                shift_slot_id=_stored_artifact_id(run.id, assignment.slot_id),
                role_id=assignment.role_id,
                employee_id=assignment.employee_id,
                employee_name=assignment.employee_name,
                source=assignment.source,
                locked_by_user=assignment.locked_by_user,
                warning_state=assignment.warning_state,
                warning_message=assignment.warning_message,
                attempt_no=assignment.attempt_no,
            )
            for assignment in artifacts.assignments
        ]
    )
    db_session.add_all(
        [
            ScheduleIssueRecord(
                id=_stored_artifact_id(run.id, issue.id),
                organization_id=run.organization_id,
                schedule_run_id=run.id,
                shift_slot_id=(
                    _stored_artifact_id(run.id, issue.slot_id)
                    if issue.slot_id is not None
                    else None
                ),
                role_id=issue.role_id,
                type=issue.type,
                missing_count=issue.missing_count,
                severity=issue.severity,
                reason_code=issue.reason_code,
                display_message=issue.display_message,
                related_proposal_ids_json=json.dumps(
                    issue.related_proposal_ids,
                    ensure_ascii=False,
                ),
                attempt_no=issue.attempt_no,
            )
            for issue in artifacts.issues
        ]
    )
    db_session.add_all(
        [
            RelaxationProposalRecord(
                id=_stored_artifact_id(run.id, proposal.id),
                organization_id=run.organization_id,
                schedule_run_id=run.id,
                group_id=proposal.group_id,
                requires_proposal_ids_json=json.dumps(
                    proposal.requires_proposal_ids,
                    ensure_ascii=False,
                ),
                type=proposal.type,
                severity=proposal.severity,
                affected_shift_slot_id=(
                    _stored_artifact_id(run.id, proposal.affected_slot_id)
                    if proposal.affected_slot_id is not None
                    else None
                ),
                display_summary=proposal.display_summary,
                impact_preview_json=json.dumps(
                    proposal.impact_preview.model_dump(mode="json"),
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                status=proposal.status,
                attempt_no=proposal.attempt_no,
            )
            for proposal in artifacts.proposals
        ]
    )
    db_session.add_all(_diagnostic_events_for_artifacts(run, artifacts))
    db_session.flush()


def _merge_locked_manual_assignments(
    *,
    run: ScheduleRun,
    artifacts: _MockArtifacts,
    db_session: Session,
) -> _MockArtifacts:
    manual_assignments = [
        _assignment_response_from_record(run, assignment)
        for assignment in db_session.execute(
            select(AssignmentRecord).where(
                AssignmentRecord.organization_id == run.organization_id,
                AssignmentRecord.schedule_run_id == run.id,
                AssignmentRecord.source == "manual",
                AssignmentRecord.locked_by_user.is_(True),
            )
        ).scalars()
    ]
    if not manual_assignments:
        return artifacts

    manual_keys = {
        (assignment.slot_id, assignment.role_id)
        for assignment in manual_assignments
    }
    manual_employee_slot_keys = {
        (assignment.slot_id, assignment.employee_id)
        for assignment in manual_assignments
    }
    assignments = [
        assignment
        for assignment in artifacts.assignments
        if (assignment.slot_id, assignment.role_id) not in manual_keys
        and (assignment.slot_id, assignment.employee_id)
        not in manual_employee_slot_keys
    ]
    assignments.extend(manual_assignments)

    issues = [
        issue
        for issue in artifacts.issues
        if (issue.slot_id, issue.role_id) not in manual_keys
    ]
    removed_issue_ids = {
        issue.id
        for issue in artifacts.issues
        if (issue.slot_id, issue.role_id) in manual_keys
    }
    manual_slot_ids = {assignment.slot_id for assignment in manual_assignments}
    proposals = [
        proposal
        for proposal in artifacts.proposals
        if proposal.affected_slot_id not in manual_slot_ids
        and not set(proposal.impact_preview.resolved_issue_ids).intersection(
            removed_issue_ids
        )
    ]
    _attach_related_proposal_ids(issues, proposals)
    return _MockArtifacts(
        slots=artifacts.slots,
        requirements=artifacts.requirements,
        assignments=sorted(
            assignments,
            key=lambda assignment: (
                assignment.slot_id,
                assignment.role_id,
                assignment.id,
            ),
        ),
        issues=issues,
        proposals=proposals,
        score_summary=ScoreSummary(
            hard=0,
            approvable=0,
            soft=sum(issue.missing_count * 100 for issue in issues),
            severity_label="high" if issues else "none",
        ),
    )


def _diagnostic_events_for_artifacts(
    run: ScheduleRun,
    artifacts: _MockArtifacts,
) -> list[SolverDiagnosticEventRecord]:
    events: list[SolverDiagnosticEventRecord] = []
    for issue in artifacts.issues:
        events.append(
            SolverDiagnosticEventRecord(
                id=_stored_artifact_id(run.id, f"diag_issue_{issue.id}"),
                organization_id=run.organization_id,
                schedule_run_id=run.id,
                event_type="infeasibility_core",
                shift_slot_id=(
                    _stored_artifact_id(run.id, issue.slot_id)
                    if issue.slot_id is not None
                    else None
                ),
                role_id=issue.role_id,
                employee_id=None,
                related_employee_ids_json="[]",
                constraint_type=issue.type,
                constraint_id=issue.id,
                metadata_json=json.dumps(
                    {
                        "reason_code": issue.reason_code,
                        "missing_count": issue.missing_count,
                        "related_proposal_ids": issue.related_proposal_ids,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                attempt_no=issue.attempt_no,
            )
        )

    for proposal in artifacts.proposals:
        parsed_time_off = _parse_time_off_proposal_id(proposal.id)
        if parsed_time_off is not None:
            employee_id, _slot_id = parsed_time_off
            event_type = "unary_exclusion"
            constraint_type = "unavailability"
            related_employee_ids = [employee_id]
        elif proposal.type == "mark_manual_review":
            employee_id = None
            event_type = "manual_review"
            constraint_type = "no_relaxation_candidate"
            related_employee_ids = []
        else:
            employee_id = None
            event_type = "relational_conflict"
            constraint_type = proposal.type
            related_employee_ids = []

        events.append(
            SolverDiagnosticEventRecord(
                id=_stored_artifact_id(run.id, f"diag_proposal_{proposal.id}"),
                organization_id=run.organization_id,
                schedule_run_id=run.id,
                event_type=event_type,
                shift_slot_id=(
                    _stored_artifact_id(run.id, proposal.affected_slot_id)
                    if proposal.affected_slot_id is not None
                    else None
                ),
                role_id=None,
                employee_id=employee_id,
                related_employee_ids_json=json.dumps(
                    related_employee_ids,
                    ensure_ascii=False,
                ),
                constraint_type=constraint_type,
                constraint_id=proposal.id,
                metadata_json=json.dumps(
                    {
                        "proposal_type": proposal.type,
                        "proposal_status": proposal.status,
                        "display_summary": proposal.display_summary,
                        "resolved_issue_ids": (
                            proposal.impact_preview.resolved_issue_ids
                        ),
                        "unavailable_reasons": (
                            proposal.impact_preview.unavailable_reasons
                        ),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                attempt_no=proposal.attempt_no,
            )
        )
    return events


def _load_persisted_artifacts(
    run: ScheduleRun,
    db_session: Session,
) -> _MockArtifacts | None:
    slots = list(
        db_session.execute(
            select(ShiftSlotRecord)
            .where(ShiftSlotRecord.schedule_run_id == run.id)
            .order_by(ShiftSlotRecord.local_date, ShiftSlotRecord.id)
        ).scalars()
    )
    if not slots:
        return None
    requirements = list(
        db_session.execute(
            select(ScheduleRequirementRecord)
            .where(ScheduleRequirementRecord.schedule_run_id == run.id)
            .order_by(ScheduleRequirementRecord.shift_slot_id, ScheduleRequirementRecord.id)
        ).scalars()
    )
    assignments = list(
        db_session.execute(
            select(AssignmentRecord)
            .where(AssignmentRecord.schedule_run_id == run.id)
            .order_by(AssignmentRecord.shift_slot_id, AssignmentRecord.role_id, AssignmentRecord.id)
        ).scalars()
    )
    issues = list(
        db_session.execute(
            select(ScheduleIssueRecord)
            .where(ScheduleIssueRecord.schedule_run_id == run.id)
            .order_by(ScheduleIssueRecord.id)
        ).scalars()
    )
    proposals = list(
        db_session.execute(
            select(RelaxationProposalRecord)
            .where(RelaxationProposalRecord.schedule_run_id == run.id)
            .order_by(RelaxationProposalRecord.id)
        ).scalars()
    )
    return _MockArtifacts(
        slots=[
            ShiftSlotResponse(
                id=_external_artifact_id(run.id, slot.id),
                local_date=slot.local_date,
                label=slot.label,
                starts_at=slot.starts_at,
                ends_at=slot.ends_at,
            )
            for slot in slots
        ],
        requirements=[
            ShiftRequirementResponse(
                id=_external_artifact_id(run.id, requirement.id),
                slot_id=_external_artifact_id(run.id, requirement.shift_slot_id),
                role_id=requirement.role_id,
                role_name=requirement.role_name,
                required_count=requirement.required_count,
            )
            for requirement in requirements
        ],
        assignments=[
            AssignmentResponse(
                id=_external_artifact_id(run.id, assignment.id),
                slot_id=_external_artifact_id(run.id, assignment.shift_slot_id),
                role_id=assignment.role_id,
                employee_id=assignment.employee_id,
                employee_name=assignment.employee_name,
                source=assignment.source,
                locked_by_user=assignment.locked_by_user,
                warning_state=assignment.warning_state,
                warning_message=assignment.warning_message,
                attempt_no=assignment.attempt_no,
            )
            for assignment in assignments
        ],
        issues=[
            ScheduleIssueResponse(
                id=_external_artifact_id(run.id, issue.id),
                slot_id=(
                    _external_artifact_id(run.id, issue.shift_slot_id)
                    if issue.shift_slot_id is not None
                    else None
                ),
                role_id=issue.role_id,
                type=issue.type,
                missing_count=issue.missing_count,
                severity=issue.severity,
                reason_code=issue.reason_code,
                display_message=issue.display_message,
                attempt_no=issue.attempt_no,
                related_proposal_ids=json.loads(issue.related_proposal_ids_json),
            )
            for issue in issues
        ],
        proposals=[
            RelaxationProposalResponse(
                id=_external_artifact_id(run.id, proposal.id),
                group_id=proposal.group_id,
                requires_proposal_ids=json.loads(proposal.requires_proposal_ids_json),
                type=proposal.type,
                severity=proposal.severity,
                affected_slot_id=(
                    _external_artifact_id(run.id, proposal.affected_shift_slot_id)
                    if proposal.affected_shift_slot_id is not None
                    else None
                ),
                display_summary=proposal.display_summary,
                impact_preview=ImpactPreview.model_validate_json(
                    proposal.impact_preview_json
                ),
                status=proposal.status,
                attempt_no=proposal.attempt_no,
                llm_explanation=_llm_explanation(),
            )
            for proposal in proposals
        ],
        score_summary=ScoreSummary(
            hard=0,
            approvable=0,
            soft=sum(issue.missing_count * 100 for issue in issues),
            severity_label="high" if issues else "none",
        ),
    )


def _result_snapshot_payload(artifacts: _MockArtifacts) -> dict[str, object]:
    return {
        "slots": [slot.model_dump(mode="json") for slot in artifacts.slots],
        "requirements": [
            requirement.model_dump(mode="json")
            for requirement in artifacts.requirements
        ],
        "assignments": [
            assignment.model_dump(mode="json")
            for assignment in artifacts.assignments
        ],
        "issues": [issue.model_dump(mode="json") for issue in artifacts.issues],
        "proposals": [
            proposal.model_dump(mode="json")
            for proposal in artifacts.proposals
        ],
        "score_summary": artifacts.score_summary.model_dump(mode="json"),
    }


def _artifacts_from_publication_snapshot(
    publication: SchedulePublication,
) -> _MockArtifacts:
    payload = json.loads(publication.result_snapshot_json or "{}")
    return _MockArtifacts(
        slots=[ShiftSlotResponse.model_validate(item) for item in payload["slots"]],
        requirements=[
            ShiftRequirementResponse.model_validate(item)
            for item in payload["requirements"]
        ],
        assignments=[
            AssignmentResponse.model_validate(item)
            for item in payload["assignments"]
        ],
        issues=[
            ScheduleIssueResponse.model_validate(item)
            for item in payload["issues"]
        ],
        proposals=[
            RelaxationProposalResponse.model_validate(item)
            for item in payload["proposals"]
        ],
        score_summary=ScoreSummary.model_validate(payload["score_summary"]),
    )


def _shift_type_id_from_slot_id(slot_id: str) -> str | None:
    marker = "_shift_type_"
    if marker not in slot_id:
        return None
    return "shift_type_" + slot_id.split(marker, 1)[1]


def _stored_artifact_id(run_id: str, artifact_id: str) -> str:
    return f"{run_id}__{artifact_id}"


def _external_artifact_id(run_id: str, stored_id: str) -> str:
    prefix = f"{run_id}__"
    return stored_id[len(prefix) :] if stored_id.startswith(prefix) else stored_id


def _mock_result_artifacts(
    run: ScheduleRun,
    db_session: Session,
) -> _MockArtifacts:
    shift_types = list(
        db_session.execute(
            select(ShiftType).where(
                ShiftType.organization_id == run.organization_id,
                ShiftType.active.is_(True),
            )
        ).scalars()
    )
    if shift_types:
        return _solver_result_artifacts(run, db_session, shift_types)

    roles = list(
        db_session.execute(
            select(Role).where(Role.organization_id == run.organization_id)
        ).scalars()
    )
    roles.sort(key=lambda role: ({"사수": 0, "부사수": 1}.get(role.name, 100), role.name))
    employees = list(
        db_session.execute(
            select(Employee).where(
                Employee.organization_id == run.organization_id,
                Employee.active.is_(True),
            )
        ).scalars()
    )
    employees.sort(key=lambda employee: employee.employee_code)

    slots = _mock_slots(run)
    requirements: list[ShiftRequirementResponse] = []
    assignments: list[AssignmentResponse] = []
    assignment_no = 1
    should_resolve_unfilled = _should_resolve_mock_unfilled(run, db_session)
    skipped_unfilled = False
    for slot in slots:
        for role in roles:
            requirement = ShiftRequirementResponse(
                id=f"req_{slot.id}_{role.id}",
                slot_id=slot.id,
                role_id=role.id,
                role_name=role.name,
                required_count=1,
            )
            requirements.append(requirement)
            if role.name == "부사수" and not skipped_unfilled and not should_resolve_unfilled:
                skipped_unfilled = True
                continue
            if not employees:
                continue
            employee = employees[(assignment_no - 1) % len(employees)]
            assignments.append(
                AssignmentResponse(
                    id=f"assign_mock_{assignment_no}",
                    slot_id=slot.id,
                    role_id=role.id,
                    employee_id=employee.id,
                    employee_name=employee.name,
                    source="solver",
                    locked_by_user=False,
                    warning_state="none",
                    warning_message=None,
                    attempt_no=run.current_attempt_no,
                )
            )
            assignment_no += 1

    issues = _mock_issues(run, roles, slots, skipped_unfilled)
    approved_proposal_ids = set(
        db_session.execute(
            select(OverrideApproval.relaxation_proposal_id).where(
                OverrideApproval.organization_id == run.organization_id,
                OverrideApproval.schedule_run_id == run.id,
            )
        ).scalars()
    )
    proposals = _mock_proposals(run, issues, approved_proposal_ids)
    score_summary = ScoreSummary(
        hard=0,
        approvable=0,
        soft=100 if issues else 0,
        severity_label="high" if issues else "none",
    )
    return _MockArtifacts(
        slots=slots,
        requirements=requirements,
        assignments=assignments,
        issues=issues,
        proposals=proposals,
        score_summary=score_summary,
    )


def _solver_result_artifacts(
    run: ScheduleRun,
    db_session: Session,
    shift_types: list[ShiftType],
) -> _MockArtifacts:
    shift_types.sort(key=lambda shift_type: shift_type.name)
    roles = list(
        db_session.execute(
            select(Role).where(Role.organization_id == run.organization_id)
        ).scalars()
    )
    role_by_id = {role.id: role for role in roles}
    shift_type_ids = [shift_type.id for shift_type in shift_types]
    db_requirements = list(
        db_session.execute(
            select(ShiftRequirement).where(
                ShiftRequirement.organization_id == run.organization_id,
                ShiftRequirement.shift_type_id.in_(shift_type_ids),
            )
        ).scalars()
    )
    requirements_by_shift_type: dict[str, list[ShiftRequirement]] = {
        shift_type.id: [] for shift_type in shift_types
    }
    for requirement in db_requirements:
        requirements_by_shift_type[requirement.shift_type_id].append(requirement)
    for requirements in requirements_by_shift_type.values():
        requirements.sort(key=lambda requirement: role_by_id[requirement.role_id].name)

    slots = _solver_slots(run, shift_types)
    shift_type_by_slot_id = {
        slot.id: shift_type
        for slot, shift_type in _solver_slot_pairs(run, shift_types)
    }
    response_requirements: list[ShiftRequirementResponse] = []
    solver_requirements: list[ScheduleRequirementInput] = []
    for slot in slots:
        shift_type = shift_type_by_slot_id[slot.id]
        for requirement in requirements_by_shift_type[shift_type.id]:
            response_requirement = ShiftRequirementResponse(
                id=f"req_{slot.id}_{requirement.id}",
                slot_id=slot.id,
                role_id=requirement.role_id,
                role_name=role_by_id[requirement.role_id].name,
                required_count=requirement.required_count,
            )
            response_requirements.append(response_requirement)
            solver_requirements.append(
                ScheduleRequirementInput(
                    id=response_requirement.id,
                    slot_id=slot.id,
                    role_id=requirement.role_id,
                    required_count=requirement.required_count,
                    unfilled_weight=requirement.unfilled_weight_override or 100,
                )
            )

    employees = list(
        db_session.execute(
            select(Employee).where(
                Employee.organization_id == run.organization_id,
                Employee.active.is_(True),
            )
        ).scalars()
    )
    employees.sort(key=lambda employee: employee.employee_code)
    role_ids_by_employee = _role_ids_by_employee(run.organization_id, db_session)
    unavailable_slot_ids_by_employee = _unavailable_slot_ids_by_employee(
        run=run,
        slots=slots,
        db_session=db_session,
    )
    solver_employees = [
        EmployeeInput(
            id=employee.id,
            role_ids=frozenset(role_ids_by_employee.get(employee.id, set())),
            unavailable_slot_ids=frozenset(
                unavailable_slot_ids_by_employee.get(employee.id, set())
            ),
        )
        for employee in employees
    ]
    solver_slots = [
        ScheduleSlotInput(id=slot.id, local_date=slot.local_date.isoformat())
        for slot in slots
    ]
    solver_result = solve_schedule(
        SolveScheduleRequest(
            employees=solver_employees,
            slots=solver_slots,
            requirements=solver_requirements,
            blocked_pairs=_blocked_pairs(run.organization_id, db_session),
            timeout_seconds=run.timeout_seconds,
            random_seed=1,
        )
    )
    run.status = solver_result.status
    run.solver_status = solver_result.solver_status
    run.solution_quality = solver_result.solution_quality
    employee_by_id = {employee.id: employee for employee in employees}
    assignments = [
        AssignmentResponse(
            id=f"assign_solver_{index}",
            slot_id=assignment.slot_id,
            role_id=assignment.role_id,
            employee_id=assignment.employee_id,
            employee_name=employee_by_id[assignment.employee_id].name,
            source="solver",
            locked_by_user=False,
            warning_state="none",
            warning_message=None,
            attempt_no=run.current_attempt_no,
        )
        for index, assignment in enumerate(solver_result.assignments, start=1)
    ]
    requirement_by_id = {
        requirement.id: requirement for requirement in response_requirements
    }
    issues = [
        _solver_issue_response(
            run=run,
            issue_no=index,
            issue=issue,
            requirement_by_id=requirement_by_id,
        )
        for index, issue in enumerate(solver_result.issues, start=1)
    ]
    approved_proposal_ids = set(
        db_session.execute(
            select(OverrideApproval.relaxation_proposal_id).where(
                OverrideApproval.organization_id == run.organization_id,
                OverrideApproval.schedule_run_id == run.id,
            )
        ).scalars()
    )
    proposals = _solver_proposals(
        run=run,
        issues=issues,
        approved_proposal_ids=approved_proposal_ids,
        db_session=db_session,
    )
    _attach_related_proposal_ids(issues, proposals)
    return _MockArtifacts(
        slots=slots,
        requirements=response_requirements,
        assignments=assignments,
        issues=issues,
        proposals=proposals,
        score_summary=ScoreSummary(
            hard=0,
            approvable=0,
            soft=sum(issue.missing_count * 100 for issue in issues),
            severity_label="high" if issues else "none",
        ),
    )


def _solver_issue_response(
    *,
    run: ScheduleRun,
    issue_no: int,
    issue: dict[str, object],
    requirement_by_id: dict[str, ShiftRequirementResponse],
) -> ScheduleIssueResponse:
    requirement = requirement_by_id[str(issue["requirement_id"])]
    missing_count = int(issue["missing_count"])
    return ScheduleIssueResponse(
        id=f"issue_solver_unfilled_{issue_no}",
        slot_id=requirement.slot_id,
        role_id=requirement.role_id,
        type="unfilled_requirement",
        missing_count=missing_count,
        severity=str(issue["severity"]),
        reason_code="NO_AVAILABLE_CANDIDATE",
        display_message=f"{requirement.role_name} {missing_count}명이 미배정입니다.",
        attempt_no=run.current_attempt_no,
        related_proposal_ids=[],
    )


def _solver_proposals(
    *,
    run: ScheduleRun,
    issues: list[ScheduleIssueResponse],
    approved_proposal_ids: set[str],
    db_session: Session,
) -> list[RelaxationProposalResponse]:
    proposals: list[RelaxationProposalResponse] = []
    for issue in issues:
        candidates = _time_off_override_candidates(run, issue, db_session)
        if candidates and issue.slot_id is not None:
            limited_candidates = candidates[:3]
            unavailable_reasons = (
                []
                if len(limited_candidates) > 1
                else ["NO_ADDITIONAL_TIME_OFF_OVERRIDE_CANDIDATE"]
            )
            group_id = (
                f"group_{issue.id}" if len(limited_candidates) > 1 else None
            )
            for candidate in limited_candidates:
                proposal_id = _time_off_proposal_id(candidate.id, issue.slot_id)
                proposals.append(
                    RelaxationProposalResponse(
                        id=proposal_id,
                        group_id=group_id,
                        requires_proposal_ids=[],
                        type="approve_time_off_override",
                        severity=issue.severity,
                        affected_slot_id=issue.slot_id,
                        display_summary=(
                            "해당 슬롯의 휴가 중 후보 1명을 예외 승인하면 "
                            "미배정을 해소할 수 있습니다."
                        ),
                        impact_preview=ImpactPreview(
                            resolved_issue_ids=[issue.id],
                            new_warning_count=1,
                            unavailable_reasons=unavailable_reasons,
                        ),
                        status=(
                            "approved"
                            if proposal_id in approved_proposal_ids
                            else "suggested"
                        ),
                        attempt_no=run.current_attempt_no,
                        llm_explanation=_llm_explanation(),
                    )
                )
            continue

        proposal_id = f"proposal_manual_review__{issue.id}"
        proposals.append(
            RelaxationProposalResponse(
                id=proposal_id,
                group_id=None,
                requires_proposal_ids=[],
                type="mark_manual_review",
                severity=issue.severity,
                affected_slot_id=issue.slot_id,
                display_summary="자동 완화 가능한 후보가 없어 수동 검토가 필요합니다.",
                impact_preview=ImpactPreview(
                    resolved_issue_ids=[],
                    new_warning_count=0,
                    unavailable_reasons=["NO_TIME_OFF_OVERRIDE_CANDIDATE"],
                ),
                status=(
                    "approved" if proposal_id in approved_proposal_ids else "suggested"
                ),
                attempt_no=run.current_attempt_no,
                llm_explanation=_llm_explanation(),
            )
        )
    return proposals


def _attach_related_proposal_ids(
    issues: list[ScheduleIssueResponse],
    proposals: list[RelaxationProposalResponse],
) -> None:
    for issue in issues:
        issue.related_proposal_ids = [
            proposal.id
            for proposal in proposals
            if issue.id in proposal.impact_preview.resolved_issue_ids
            or proposal.affected_slot_id == issue.slot_id
        ]


def _time_off_override_candidates(
    run: ScheduleRun,
    issue: ScheduleIssueResponse,
    db_session: Session,
) -> list[Employee]:
    if issue.slot_id is None or issue.role_id is None:
        return []
    slot_date = _local_date_from_slot_id(issue.slot_id)
    if slot_date is None:
        return []
    role_ids_by_employee = _role_ids_by_employee(run.organization_id, db_session)
    eligible_employee_ids = {
        employee_id
        for employee_id, role_ids in role_ids_by_employee.items()
        if issue.role_id in role_ids
    }
    if not eligible_employee_ids:
        return []
    employees_by_id = {
        employee.id: employee
        for employee in db_session.execute(
            select(Employee).where(
                Employee.organization_id == run.organization_id,
                Employee.active.is_(True),
                Employee.id.in_(eligible_employee_ids),
            )
        ).scalars()
    }
    candidates: list[Employee] = []
    unavailabilities = db_session.execute(
        select(Unavailability).where(
            Unavailability.organization_id == run.organization_id,
            Unavailability.override_allowed.is_(True),
            Unavailability.employee_id.in_(eligible_employee_ids),
        )
    ).scalars()
    for unavailability in unavailabilities:
        if (
            _unavailability_overlaps_date(unavailability, slot_date)
            and unavailability.employee_id in employees_by_id
        ):
            candidates.append(employees_by_id[unavailability.employee_id])
    candidates.sort(key=lambda employee: employee.employee_code)
    return candidates


def _time_off_proposal_id(employee_id: str, slot_id: str) -> str:
    return f"proposal_time_off__{employee_id}__{slot_id}"


def _parse_time_off_proposal_id(proposal_id: str) -> tuple[str, str] | None:
    prefix = "proposal_time_off__"
    if not proposal_id.startswith(prefix):
        return None
    remainder = proposal_id[len(prefix) :]
    parts = remainder.split("__", 1)
    if len(parts) != 2:
        return None
    return parts[0], parts[1]


def _local_date_from_slot_id(slot_id: str) -> date | None:
    parts = slot_id.split("_")
    if len(parts) < 4 or parts[0] != "slot":
        return None
    try:
        return date(int(parts[1]), int(parts[2]), int(parts[3]))
    except ValueError:
        return None


def _solver_slots(
    run: ScheduleRun,
    shift_types: list[ShiftType],
) -> list[ShiftSlotResponse]:
    return [slot for slot, _shift_type in _solver_slot_pairs(run, shift_types)]


def _solver_slot_pairs(
    run: ScheduleRun,
    shift_types: list[ShiftType],
) -> list[tuple[ShiftSlotResponse, ShiftType]]:
    return _generated_slot_pairs(run.period_start, run.period_end, shift_types)


def _generated_slot_pairs(
    period_start: date,
    period_end: date,
    shift_types: list[ShiftType],
) -> list[tuple[ShiftSlotResponse, ShiftType]]:
    slot_pairs: list[tuple[ShiftSlotResponse, ShiftType]] = []
    current_date = period_start
    while current_date <= period_end:
        date_token = current_date.isoformat().replace("-", "_")
        for shift_type in shift_types:
            slot = ShiftSlotResponse(
                id=f"slot_{date_token}_{shift_type.id}",
                local_date=current_date,
                label=shift_type.name,
                starts_at=_local_datetime(current_date, shift_type.local_start_time),
                ends_at=_local_datetime(current_date, shift_type.local_end_time),
            )
            slot_pairs.append((slot, shift_type))
        current_date += timedelta(days=1)
    return slot_pairs


def _generated_snapshot_artifacts(
    *,
    period_start: date,
    period_end: date,
    shift_types: list[ShiftType],
    shift_requirements: list[ShiftRequirement],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    active_shift_types = sorted(
        [shift_type for shift_type in shift_types if shift_type.active],
        key=lambda shift_type: (shift_type.name, shift_type.id),
    )
    requirements_by_shift_type: dict[str, list[ShiftRequirement]] = {
        shift_type.id: [] for shift_type in active_shift_types
    }
    for requirement in shift_requirements:
        if requirement.shift_type_id in requirements_by_shift_type:
            requirements_by_shift_type[requirement.shift_type_id].append(requirement)
    for requirements in requirements_by_shift_type.values():
        requirements.sort(key=lambda requirement: (requirement.role_id, requirement.id))

    generated_slots: list[dict[str, object]] = []
    generated_requirements: list[dict[str, object]] = []
    for slot, shift_type in _generated_slot_pairs(
        period_start,
        period_end,
        active_shift_types,
    ):
        generated_slots.append(
            {
                "id": slot.id,
                "shift_type_id": shift_type.id,
                "local_date": slot.local_date.isoformat(),
                "label": slot.label,
                "starts_at": slot.starts_at,
                "ends_at": slot.ends_at,
            }
        )
        for requirement in requirements_by_shift_type[shift_type.id]:
            generated_requirements.append(
                {
                    "id": f"req_{slot.id}_{requirement.id}",
                    "slot_id": slot.id,
                    "shift_type_id": shift_type.id,
                    "shift_requirement_id": requirement.id,
                    "role_id": requirement.role_id,
                    "required_count": requirement.required_count,
                    "unfilled_weight_override": requirement.unfilled_weight_override,
                }
            )
    return generated_slots, generated_requirements


def _local_datetime(local_date: date, local_time: str) -> str:
    hour_minute = local_time if len(local_time) == 5 else local_time[:5]
    return f"{local_date.isoformat()}T{hour_minute}:00+09:00"


def _role_ids_by_employee(
    organization_id: str,
    db_session: Session,
) -> dict[str, set[str]]:
    role_links = db_session.execute(
        select(EmployeeRole).where(
            EmployeeRole.organization_id == organization_id,
            EmployeeRole.active.is_(True),
        )
    ).scalars()
    role_ids_by_employee: dict[str, set[str]] = {}
    for role_link in role_links:
        role_ids_by_employee.setdefault(role_link.employee_id, set()).add(
            role_link.role_id
        )
    return role_ids_by_employee


def _unavailable_slot_ids_by_employee(
    *,
    run: ScheduleRun,
    slots: list[ShiftSlotResponse],
    db_session: Session,
) -> dict[str, set[str]]:
    unavailabilities = list(
        db_session.execute(
            select(Unavailability).where(
                Unavailability.organization_id == run.organization_id
            )
        ).scalars()
    )
    approved_time_off_pairs = {
        parsed
        for proposal_id in db_session.execute(
            select(OverrideApproval.relaxation_proposal_id).where(
                OverrideApproval.organization_id == run.organization_id,
                OverrideApproval.schedule_run_id == run.id,
                OverrideApproval.type == "approve_time_off_override",
            )
        ).scalars()
        if (parsed := _parse_time_off_proposal_id(proposal_id)) is not None
    }
    legacy_run_wide_override = db_session.execute(
        select(OverrideApproval.id).where(
            OverrideApproval.organization_id == run.organization_id,
            OverrideApproval.schedule_run_id == run.id,
            OverrideApproval.type == "approve_time_off_override",
            OverrideApproval.relaxation_proposal_id == "proposal_mock_time_off_1",
        )
    ).first()
    slot_ids_by_employee: dict[str, set[str]] = {}
    for unavailability in unavailabilities:
        for slot in slots:
            if (
                unavailability.override_allowed
                and (
                    legacy_run_wide_override is not None
                    or (unavailability.employee_id, slot.id) in approved_time_off_pairs
                )
            ):
                continue
            if _unavailability_overlaps_date(unavailability, slot.local_date):
                slot_ids_by_employee.setdefault(unavailability.employee_id, set()).add(
                    slot.id
                )
    return slot_ids_by_employee


def _unavailability_overlaps_date(
    unavailability: Unavailability,
    local_date: date,
) -> bool:
    start_date = unavailability.starts_at.date()
    end_date = unavailability.ends_at.date()
    if unavailability.ends_at.time().isoformat() == "00:00:00":
        return start_date <= local_date < end_date
    return start_date <= local_date <= end_date


def _blocked_pairs(
    organization_id: str,
    db_session: Session,
) -> list[BlockedPair]:
    pair_constraints = db_session.execute(
        select(PairConstraint).where(
            PairConstraint.organization_id == organization_id,
            PairConstraint.type == "blocked",
            PairConstraint.active.is_(True),
        )
    ).scalars()
    return [
        BlockedPair(
            pair_constraint.normalized_employee_a_id,
            pair_constraint.normalized_employee_b_id,
        )
        for pair_constraint in pair_constraints
    ]


def _should_resolve_mock_unfilled(
    run: ScheduleRun,
    db_session: Session,
) -> bool:
    if run.recalculation_count <= 0:
        return False
    approved_override = db_session.execute(
        select(OverrideApproval.id).where(
            OverrideApproval.organization_id == run.organization_id,
            OverrideApproval.schedule_run_id == run.id,
        )
    ).first()
    return approved_override is not None


def _mock_slots(run: ScheduleRun) -> list[ShiftSlotResponse]:
    slots: list[ShiftSlotResponse] = []
    current_date = run.period_start
    while current_date <= run.period_end:
        date_token = current_date.isoformat().replace("-", "_")
        slots.append(
            ShiftSlotResponse(
                id=f"slot_{date_token}_day",
                local_date=current_date,
                label="주간 근무",
                starts_at=f"{current_date.isoformat()}T09:00:00+09:00",
                ends_at=f"{current_date.isoformat()}T18:00:00+09:00",
            )
        )
        current_date += timedelta(days=1)
    return slots


def _mock_issues(
    run: ScheduleRun,
    roles: list[Role],
    slots: list[ShiftSlotResponse],
    skipped_unfilled: bool,
) -> list[ScheduleIssueResponse]:
    junior_role = next((role for role in roles if role.name == "부사수"), None)
    if junior_role is None or not slots or not skipped_unfilled:
        return []
    return [
        ScheduleIssueResponse(
            id="issue_mock_unfilled_1",
            slot_id=slots[0].id,
            role_id=junior_role.id,
            type="unfilled_requirement",
            missing_count=1,
            severity="high",
            reason_code="NO_AVAILABLE_CANDIDATE",
            display_message="부사수 1명이 미배정입니다.",
            attempt_no=run.current_attempt_no,
            related_proposal_ids=["proposal_mock_time_off_1"],
        )
    ]


def _mock_proposals(
    run: ScheduleRun,
    issues: list[ScheduleIssueResponse],
    approved_proposal_ids: set[str],
) -> list[RelaxationProposalResponse]:
    if not issues:
        return []
    proposal_id = "proposal_mock_time_off_1"
    return [
        RelaxationProposalResponse(
            id=proposal_id,
            group_id=None,
            requires_proposal_ids=[],
            type="approve_time_off_override",
            severity="high",
            affected_slot_id=issues[0].slot_id,
            display_summary="휴가 중인 후보 1명을 예외 승인하면 미배정을 해소할 수 있습니다.",
            impact_preview=ImpactPreview(
                resolved_issue_ids=[issues[0].id],
                new_warning_count=1,
            ),
            status="approved" if proposal_id in approved_proposal_ids else "suggested",
            attempt_no=run.current_attempt_no,
            llm_explanation=_llm_explanation(),
        )
    ]


def _validate_manual_edit_request(
    *,
    organization_id: str,
    request: ManualEditValidationRequest,
    artifacts: _MockArtifacts,
    db_session: Session,
) -> ManualEditValidationResponse:
    blocking_errors: list[FieldErrorResponse] = []
    warnings: list[FieldErrorResponse] = []

    slot = next((item for item in artifacts.slots if item.id == request.slot_id), None)
    if slot is None:
        blocking_errors.append(
            _field_error(
                "slot_id",
                "SLOT_NOT_FOUND",
                "Shift slot does not exist in this ScheduleRun.",
            )
        )

    role = db_session.get(Role, request.role_id)
    if role is None or role.organization_id != organization_id:
        blocking_errors.append(
            _field_error(
                "role_id",
                "ROLE_NOT_FOUND",
                "Role does not exist in this organization.",
            )
        )

    employee = db_session.get(Employee, request.employee_id)
    if (
        employee is None
        or employee.organization_id != organization_id
        or not employee.active
    ):
        blocking_errors.append(
            _field_error(
                "employee_id",
                "EMPLOYEE_NOT_FOUND",
                "Active employee does not exist in this organization.",
            )
        )

    if role is not None and employee is not None:
        role_link = db_session.execute(
            select(EmployeeRole).where(
                EmployeeRole.organization_id == organization_id,
                EmployeeRole.employee_id == request.employee_id,
                EmployeeRole.role_id == request.role_id,
                EmployeeRole.active.is_(True),
            )
        ).scalar_one_or_none()
        if role_link is None:
            blocking_errors.append(
                _field_error(
                    "employee_id",
                    "EMPLOYEE_ROLE_MISMATCH",
                    "Employee is not eligible for the requested role.",
                )
            )

    if slot is not None and employee is not None:
        _validate_manual_unavailability(
            organization_id=organization_id,
            employee_id=request.employee_id,
            slot=slot,
            blocking_errors=blocking_errors,
            warnings=warnings,
            db_session=db_session,
        )
        _validate_manual_blocked_pairs(
            organization_id=organization_id,
            employee_id=request.employee_id,
            slot_id=request.slot_id,
            assignments=artifacts.assignments,
            blocking_errors=blocking_errors,
            db_session=db_session,
        )

    return ManualEditValidationResponse(
        valid=not blocking_errors,
        blocking_errors=blocking_errors,
        warnings=warnings,
    )


def _validate_manual_unavailability(
    *,
    organization_id: str,
    employee_id: str,
    slot: ShiftSlotResponse,
    blocking_errors: list[FieldErrorResponse],
    warnings: list[FieldErrorResponse],
    db_session: Session,
) -> None:
    unavailabilities = db_session.execute(
        select(Unavailability).where(
            Unavailability.organization_id == organization_id,
            Unavailability.employee_id == employee_id,
        )
    ).scalars()
    for unavailability in unavailabilities:
        if not _unavailability_overlaps_date(unavailability, slot.local_date):
            continue
        target = warnings if unavailability.override_allowed else blocking_errors
        target.append(
            _field_error(
                "employee_id",
                "UNAVAILABILITY_CONFLICT",
                "Employee is unavailable for this slot.",
            )
        )
        return


def _validate_manual_blocked_pairs(
    *,
    organization_id: str,
    employee_id: str,
    slot_id: str,
    assignments: list[AssignmentResponse],
    blocking_errors: list[FieldErrorResponse],
    db_session: Session,
) -> None:
    assigned_employee_ids = {
        assignment.employee_id
        for assignment in assignments
        if assignment.slot_id == slot_id and assignment.employee_id != employee_id
    }
    if not assigned_employee_ids:
        return
    blocked_pairs = db_session.execute(
        select(PairConstraint).where(
            PairConstraint.organization_id == organization_id,
            PairConstraint.type == "blocked",
            PairConstraint.active.is_(True),
        )
    ).scalars()
    for pair_constraint in blocked_pairs:
        pair = {
            pair_constraint.normalized_employee_a_id,
            pair_constraint.normalized_employee_b_id,
        }
        if employee_id in pair and pair.intersection(assigned_employee_ids):
            blocking_errors.append(
                _field_error(
                    "employee_id",
                    "PAIR_CONSTRAINT_CONFLICT",
                    "Employee is blocked with another assignment in this slot.",
                )
            )
            return


def _field_error(field: str, code: str, message: str) -> FieldErrorResponse:
    return FieldErrorResponse(field=field, code=code, message=message)


def _build_snapshot_payload(
    *,
    organization_id: str,
    request: ScheduleRunCreateRequest,
    db_session: Session,
) -> dict[str, object]:
    employees = list(
        db_session.execute(
            select(Employee).where(Employee.organization_id == organization_id)
        ).scalars()
    )
    roles = list(
        db_session.execute(
            select(Role).where(Role.organization_id == organization_id)
        ).scalars()
    )
    employee_roles = list(
        db_session.execute(
            select(EmployeeRole).where(EmployeeRole.organization_id == organization_id)
        ).scalars()
    )
    shift_types = list(
        db_session.execute(
            select(ShiftType).where(ShiftType.organization_id == organization_id)
        ).scalars()
    )
    shift_requirements = list(
        db_session.execute(
            select(ShiftRequirement).where(
                ShiftRequirement.organization_id == organization_id
            )
        ).scalars()
    )
    unavailabilities = list(
        db_session.execute(
            select(Unavailability).where(
                Unavailability.organization_id == organization_id
            )
        ).scalars()
    )
    pair_constraints = list(
        db_session.execute(
            select(PairConstraint).where(
                PairConstraint.organization_id == organization_id
            )
        ).scalars()
    )
    generated_shift_slots, generated_schedule_requirements = (
        _generated_snapshot_artifacts(
            period_start=request.period_start,
            period_end=request.period_end,
            shift_types=shift_types,
            shift_requirements=shift_requirements,
        )
    )
    return {
        "organization_id": organization_id,
        "period_start": request.period_start.isoformat(),
        "period_end": request.period_end.isoformat(),
        "template": request.template,
        "deterministic_mode": request.deterministic_mode,
        "timeout_seconds": request.timeout_seconds,
        "employees": sorted(
            [
                {
                    "id": employee.id,
                    "employee_code": employee.employee_code,
                    "active": employee.active,
                    "max_shifts_per_week": employee.max_shifts_per_week,
                    "max_shifts_per_month": employee.max_shifts_per_month,
                }
                for employee in employees
            ],
            key=lambda item: str(item["id"]),
        ),
        "roles": sorted(
            [{"id": role.id, "name": role.name} for role in roles],
            key=lambda item: str(item["id"]),
        ),
        "employee_roles": sorted(
            [
                {
                    "employee_id": employee_role.employee_id,
                    "role_id": employee_role.role_id,
                    "priority": employee_role.priority,
                    "active": employee_role.active,
                }
                for employee_role in employee_roles
            ],
            key=lambda item: (str(item["employee_id"]), str(item["role_id"])),
        ),
        "shift_types": sorted(
            [
                {
                    "id": shift_type.id,
                    "name": shift_type.name,
                    "local_start_time": shift_type.local_start_time,
                    "local_end_time": shift_type.local_end_time,
                    "timezone": shift_type.timezone,
                    "crosses_midnight": shift_type.crosses_midnight,
                    "active": shift_type.active,
                }
                for shift_type in shift_types
            ],
            key=lambda item: str(item["id"]),
        ),
        "shift_requirements": sorted(
            [
                {
                    "id": requirement.id,
                    "shift_type_id": requirement.shift_type_id,
                    "role_id": requirement.role_id,
                    "required_count": requirement.required_count,
                    "unfilled_weight_override": requirement.unfilled_weight_override,
                }
                for requirement in shift_requirements
            ],
            key=lambda item: str(item["id"]),
        ),
        "generated_shift_slots": generated_shift_slots,
        "generated_schedule_requirements": generated_schedule_requirements,
        "unavailabilities": sorted(
            [
                {
                    "employee_id": unavailability.employee_id,
                    "type": unavailability.type,
                    "starts_at": unavailability.starts_at.isoformat(),
                    "ends_at": unavailability.ends_at.isoformat(),
                    "override_allowed": unavailability.override_allowed,
                }
                for unavailability in unavailabilities
            ],
            key=lambda item: (str(item["employee_id"]), str(item["starts_at"])),
        ),
        "pair_constraints": sorted(
            [
                {
                    "employee_a_id": pair_constraint.employee_a_id,
                    "employee_b_id": pair_constraint.employee_b_id,
                    "type": pair_constraint.type,
                    "severity": pair_constraint.severity,
                    "override_allowed": pair_constraint.override_allowed,
                    "active": pair_constraint.active,
                }
                for pair_constraint in pair_constraints
            ],
            key=lambda item: (str(item["employee_a_id"]), str(item["employee_b_id"])),
        ),
    }


def _snapshot_hash(snapshot_payload: dict[str, object]) -> str:
    return _stable_hash(snapshot_payload)


def _artifact_hashes(artifacts: _MockArtifacts) -> _ArtifactHashes:
    assignments = [
        assignment.model_dump(mode="json")
        for assignment in sorted(artifacts.assignments, key=lambda item: item.id)
    ]
    issues = [
        issue.model_dump(mode="json")
        for issue in sorted(artifacts.issues, key=lambda item: item.id)
    ]
    return _ArtifactHashes(
        assignment_snapshot_hash=_stable_hash({"assignments": assignments}),
        issue_snapshot_hash=_stable_hash({"issues": issues}),
    )


def _stable_hash(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _llm_explanation() -> LLMExplanation:
    return LLMExplanation(**fallback_explanation())


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _build_schedule_workbook(
    publication: SchedulePublication,
    artifacts: _MockArtifacts,
) -> bytes:
    rows = _schedule_export_rows(publication, artifacts)
    sheet_xml = _worksheet_xml(rows)
    workbook = BytesIO()
    with zipfile.ZipFile(workbook, mode="w", compression=zipfile.ZIP_DEFLATED) as xlsx:
        xlsx.writestr("[Content_Types].xml", _content_types_xml())
        xlsx.writestr("_rels/.rels", _root_relationships_xml())
        xlsx.writestr("xl/workbook.xml", _workbook_xml())
        xlsx.writestr("xl/_rels/workbook.xml.rels", _workbook_relationships_xml())
        xlsx.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return workbook.getvalue()


def _schedule_export_rows(
    publication: SchedulePublication,
    artifacts: _MockArtifacts,
) -> list[list[str]]:
    slots_by_id = {slot.id: slot for slot in artifacts.slots}
    role_names_by_requirement = {
        (requirement.slot_id, requirement.role_id): requirement.role_name
        for requirement in artifacts.requirements
    }
    rows = [
        [
            "publication_id",
            "local_date",
            "slot_label",
            "role_name",
            "employee_name",
            "source",
            "warning_state",
        ]
    ]
    for assignment in artifacts.assignments:
        slot = slots_by_id[assignment.slot_id]
        role_name = role_names_by_requirement[(assignment.slot_id, assignment.role_id)]
        rows.append(
            [
                publication.id,
                slot.local_date.isoformat(),
                slot.label,
                role_name,
                assignment.employee_name,
                assignment.source,
                assignment.warning_state,
            ]
        )
    return rows


def _worksheet_xml(rows: list[list[str]]) -> str:
    row_xml = []
    for row_index, row in enumerate(rows, start=1):
        cell_xml = []
        for column_index, value in enumerate(row, start=1):
            cell_ref = f"{_column_name(column_index)}{row_index}"
            cell_xml.append(
                f'<c r="{cell_ref}" t="inlineStr"><is><t>'
                f"{xml_escape(str(value))}</t></is></c>"
            )
        row_xml.append(f'<row r="{row_index}">{"".join(cell_xml)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(row_xml)}</sheetData>'
        "</worksheet>"
    )


def _column_name(column_index: int) -> str:
    name = ""
    while column_index:
        column_index, remainder = divmod(column_index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _content_types_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )


def _root_relationships_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )


def _workbook_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Schedule" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    )


def _workbook_relationships_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
