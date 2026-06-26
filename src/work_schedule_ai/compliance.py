from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import hashlib
import json
from pydantic import BaseModel


LEGAL_DISCLAIMER = (
    "이 결과는 법률 자동 판단이 아니라 운영 검토를 돕는 경고입니다. "
    "최종 판단은 조직 정책과 최신 법령 검토를 기준으로 해야 합니다."
)


class ComplianceAssignment(BaseModel):
    employee_id: str
    employee_name: str
    slot_id: str
    local_date: str
    label: str
    starts_at: str
    ends_at: str


class ComplianceWarning(BaseModel):
    code: str
    severity: str
    publish_blocking: bool
    employee_id: str | None
    employee_name: str | None
    slot_id: str | None
    week_key: str | None = None
    snapshot_hash: str = ""
    instance_key: str = ""
    message: str
    hours: float | None = None


def compliance_warning_instance_key(
    *,
    warning_code: str,
    employee_id: str | None,
    slot_id: str | None,
    week_key: str | None,
    snapshot_hash: str,
) -> str:
    payload = [
        warning_code,
        employee_id or "",
        slot_id or "",
        week_key or "",
        snapshot_hash,
    ]
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def compliance_warning_identity_payload(
    warning: ComplianceWarning,
) -> dict[str, str | None]:
    return {
        "warning_code": warning.code,
        "employee_id": warning.employee_id,
        "slot_id": warning.slot_id,
        "week_key": warning.week_key,
        "snapshot_hash": warning.snapshot_hash,
    }


def evaluate_compliance_warnings(
    assignments: list[ComplianceAssignment],
    *,
    min_rest_hours: int = 11,
) -> list[ComplianceWarning]:
    snapshot_hash = _assignment_snapshot_hash(assignments)
    warnings: list[ComplianceWarning] = []
    warnings.extend(_weekly_hours_warnings(assignments))
    warnings.extend(_minimum_rest_warnings(assignments, min_rest_hours))
    warnings.extend(_night_and_weekend_warnings(assignments))
    warnings.extend(_consecutive_night_warnings(assignments))
    return [_with_instance_identity(warning, snapshot_hash) for warning in warnings]


def _weekly_hours_warnings(
    assignments: list[ComplianceAssignment],
) -> list[ComplianceWarning]:
    hours_by_employee_week: dict[tuple[str, str], float] = defaultdict(float)
    names: dict[str, str] = {}
    for assignment in assignments:
        start = _parse_datetime(assignment.starts_at)
        end = _parse_datetime(assignment.ends_at)
        week_key = _iso_week_key(start)
        hours_by_employee_week[(assignment.employee_id, week_key)] += (
            end - start
        ).total_seconds() / 3600
        names[assignment.employee_id] = assignment.employee_name
    warnings = []
    for (employee_id, week_key), hours in hours_by_employee_week.items():
        if hours > 52:
            warnings.append(
                ComplianceWarning(
                    code="WEEKLY_HOURS_OVER_52",
                    severity="blocking",
                    publish_blocking=True,
                    employee_id=employee_id,
                    employee_name=names.get(employee_id),
                    slot_id=None,
                    week_key=week_key,
                    message="주간 예정 근무 시간이 52시간을 초과합니다.",
                    hours=round(hours, 2),
                )
            )
    return warnings


def _minimum_rest_warnings(
    assignments: list[ComplianceAssignment],
    min_rest_hours: int,
) -> list[ComplianceWarning]:
    by_employee: dict[str, list[ComplianceAssignment]] = defaultdict(list)
    for assignment in assignments:
        by_employee[assignment.employee_id].append(assignment)
    warnings = []
    for employee_id, employee_assignments in by_employee.items():
        sorted_assignments = sorted(
            employee_assignments,
            key=lambda item: _parse_datetime(item.starts_at),
        )
        for previous, current in zip(sorted_assignments, sorted_assignments[1:]):
            rest_hours = (
                _parse_datetime(current.starts_at) - _parse_datetime(previous.ends_at)
            ).total_seconds() / 3600
            if rest_hours < min_rest_hours:
                warnings.append(
                    ComplianceWarning(
                        code="MIN_REST_UNDER_POLICY",
                        severity="warning",
                        publish_blocking=False,
                        employee_id=employee_id,
                        employee_name=current.employee_name,
                        slot_id=current.slot_id,
                        message="정책상 최소 휴식 시간보다 짧은 간격이 있습니다.",
                        hours=round(rest_hours, 2),
                    )
                )
    return warnings


def _night_and_weekend_warnings(
    assignments: list[ComplianceAssignment],
) -> list[ComplianceWarning]:
    warnings = []
    for assignment in assignments:
        start = _parse_datetime(assignment.starts_at)
        if "야간" in assignment.label or start.hour >= 22 or start.hour < 6:
            warnings.append(
                ComplianceWarning(
                    code="NIGHT_WORK_REVIEW",
                    severity="info",
                    publish_blocking=False,
                    employee_id=assignment.employee_id,
                    employee_name=assignment.employee_name,
                    slot_id=assignment.slot_id,
                    message="야간 근무 수당/휴식 검토가 필요한 슬롯입니다.",
                )
            )
        if start.weekday() >= 5:
            warnings.append(
                ComplianceWarning(
                    code="WEEKEND_OR_HOLIDAY_REVIEW",
                    severity="info",
                    publish_blocking=False,
                    employee_id=assignment.employee_id,
                    employee_name=assignment.employee_name,
                    slot_id=assignment.slot_id,
                    message="휴일 또는 주말 근무 검토가 필요한 슬롯입니다.",
                )
            )
    return warnings


def _consecutive_night_warnings(
    assignments: list[ComplianceAssignment],
) -> list[ComplianceWarning]:
    by_employee: dict[str, list[ComplianceAssignment]] = defaultdict(list)
    for assignment in assignments:
        if _is_night_assignment(assignment):
            by_employee[assignment.employee_id].append(assignment)
    warnings: list[ComplianceWarning] = []
    for employee_id, employee_assignments in by_employee.items():
        sorted_assignments = sorted(
            employee_assignments,
            key=lambda item: _parse_datetime(item.starts_at),
        )
        for previous, current in zip(sorted_assignments, sorted_assignments[1:]):
            previous_start = _parse_datetime(previous.starts_at)
            current_start = _parse_datetime(current.starts_at)
            if (current_start.date() - previous_start.date()).days != 1:
                continue
            warnings.append(
                ComplianceWarning(
                    code="CONSECUTIVE_NIGHT_SHIFTS_REVIEW",
                    severity="warning",
                    publish_blocking=False,
                    employee_id=employee_id,
                    employee_name=current.employee_name,
                    slot_id=current.slot_id,
                    message=(
                        "연속 야간 근무가 예정되어 있어 피로도와 휴식 보장을 "
                        "운영 검토해야 합니다."
                    ),
                )
            )
    return warnings


def _is_night_assignment(assignment: ComplianceAssignment) -> bool:
    start = _parse_datetime(assignment.starts_at)
    return "야간" in assignment.label or start.hour >= 22 or start.hour < 6


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _iso_week_key(value: datetime) -> str:
    week = value.isocalendar()
    return f"{week.year}-W{week.week:02d}"


def _assignment_snapshot_hash(assignments: list[ComplianceAssignment]) -> str:
    payload = [
        assignment.model_dump(mode="json")
        for assignment in sorted(
            assignments,
            key=lambda item: (
                item.employee_id,
                item.slot_id,
                item.starts_at,
                item.ends_at,
            ),
        )
    ]
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _with_instance_identity(
    warning: ComplianceWarning,
    snapshot_hash: str,
) -> ComplianceWarning:
    instance_key = compliance_warning_instance_key(
        warning_code=warning.code,
        employee_id=warning.employee_id,
        slot_id=warning.slot_id,
        week_key=warning.week_key,
        snapshot_hash=snapshot_hash,
    )
    return warning.model_copy(
        update={
            "snapshot_hash": snapshot_hash,
            "instance_key": instance_key,
        }
    )
