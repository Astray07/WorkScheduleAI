from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, Text
from sqlalchemy import Index, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    timezone: Mapped[str] = mapped_column(Text, nullable=False)
    data_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'member')", name="ck_memberships_role"),
    )

    organization_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "employee_code",
            name="uq_employees_organization_employee_code",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employee_code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    seniority_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_shifts_per_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_shifts_per_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class Unavailability(Base):
    __tablename__ = "unavailabilities"
    __table_args__ = (
        CheckConstraint(
            "type IN ('vacation', 'business_trip', 'training', 'personal')",
            name="ck_unavailabilities_type",
        ),
        CheckConstraint(
            "starts_at < ends_at",
            name="ck_unavailabilities_time_order",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employee_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    ends_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    override_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_roles_organization_name"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class ShiftType(Base):
    __tablename__ = "shift_types"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "name",
            name="uq_shift_types_organization_name",
        ),
        CheckConstraint(
            "local_start_time <> local_end_time",
            name="ck_shift_types_time_not_equal",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    local_start_time: Mapped[str] = mapped_column(Text, nullable=False)
    local_end_time: Mapped[str] = mapped_column(Text, nullable=False)
    timezone: Mapped[str] = mapped_column(Text, nullable=False)
    crosses_midnight: Mapped[bool] = mapped_column(Boolean, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class ShiftRequirement(Base):
    __tablename__ = "shift_requirements"
    __table_args__ = (
        UniqueConstraint(
            "shift_type_id",
            "role_id",
            name="uq_shift_requirements_shift_type_role",
        ),
        CheckConstraint(
            "required_count >= 1",
            name="ck_shift_requirements_required_count",
        ),
        CheckConstraint(
            "unfilled_weight_override IS NULL OR unfilled_weight_override >= 0",
            name="ck_shift_requirements_unfilled_weight_override",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    shift_type_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("shift_types.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    required_count: Mapped[int] = mapped_column(Integer, nullable=False)
    unfilled_weight_override: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class EmployeeRole(Base):
    __tablename__ = "employee_roles"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "employee_id",
            "role_id",
            name="uq_employee_roles_organization_employee_role",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employee_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class PairConstraint(Base):
    __tablename__ = "pair_constraints"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "normalized_employee_a_id",
            "normalized_employee_b_id",
            "type",
            name="uq_pair_constraints_normalized_pair_type",
        ),
        CheckConstraint(
            "normalized_employee_a_id < normalized_employee_b_id",
            name="ck_pair_constraints_normalized_order",
        ),
        CheckConstraint(
            "type IN ('blocked', 'avoid', 'prefer')",
            name="ck_pair_constraints_type",
        ),
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_pair_constraints_severity",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employee_a_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
    )
    employee_b_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
    )
    normalized_employee_a_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    normalized_employee_b_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    override_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    @classmethod
    def create(
        cls,
        *,
        id: str,
        organization_id: str,
        employee_a_id: str,
        employee_b_id: str,
        type: str,
        severity: str,
        override_allowed: bool,
        active: bool = True,
    ) -> PairConstraint:
        normalized_a, normalized_b = normalize_pair_employee_ids(
            employee_a_id,
            employee_b_id,
        )
        return cls(
            id=id,
            organization_id=organization_id,
            employee_a_id=employee_a_id,
            employee_b_id=employee_b_id,
            normalized_employee_a_id=normalized_a,
            normalized_employee_b_id=normalized_b,
            type=type,
            severity=severity,
            override_allowed=override_allowed,
            active=active,
        )


class ScheduleRun(Base):
    __tablename__ = "schedule_runs"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_schedule_runs_organization_idempotency_key",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'infeasible', 'failed', 'canceled')",
            name="ck_schedule_runs_status",
        ),
        CheckConstraint(
            "solver_status IS NULL OR solver_status IN ('cp_sat_optimal', 'cp_sat_feasible', 'cp_sat_infeasible', 'cp_sat_model_invalid', 'cp_sat_unknown', 'not_started', 'error')",
            name="ck_schedule_runs_solver_status",
        ),
        CheckConstraint(
            "solution_quality IN ('optimal', 'feasible_not_proven_optimal', 'infeasible', 'unknown')",
            name="ck_schedule_runs_solution_quality",
        ),
        CheckConstraint(
            "template IN ('one_shift_per_day', 'morning_afternoon_night', 'on_call', 'custom')",
            name="ck_schedule_runs_template",
        ),
        CheckConstraint(
            "period_start <= period_end",
            name="ck_schedule_runs_period_order",
        ),
        CheckConstraint(
            "timeout_seconds >= 1 AND timeout_seconds <= 120",
            name="ck_schedule_runs_timeout_seconds",
        ),
        CheckConstraint(
            "current_attempt_no >= 1",
            name="ck_schedule_runs_current_attempt_no",
        ),
        CheckConstraint(
            "recalculation_count >= 0 AND recalculation_count <= 3",
            name="ck_schedule_runs_recalculation_count",
        ),
        Index(
            "ix_schedule_runs_organization_period",
            "organization_id",
            "period_start",
            "period_end",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    template: Mapped[str] = mapped_column(Text, nullable=False)
    deterministic_mode: Mapped[bool] = mapped_column(Boolean, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    solver_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    solution_quality: Mapped[str] = mapped_column(Text, nullable=False)
    current_attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    recalculation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    input_snapshot_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    canceled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class ScheduleInputSnapshot(Base):
    __tablename__ = "schedule_input_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "schedule_run_id",
            name="uq_schedule_input_snapshots_schedule_run_id",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    schedule_run_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("schedule_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    snapshot_hash: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    storage_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class OverrideApproval(Base):
    __tablename__ = "override_approvals"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "schedule_run_id",
            "relaxation_proposal_id",
            name="uq_override_approvals_run_proposal",
        ),
        CheckConstraint(
            "type IN ('approve_time_off_override', 'approve_pair_constraint_override', 'approve_min_rest_override', 'keep_unfilled_requirement', 'reduce_role_requirement', 'mark_manual_review')",
            name="ck_override_approvals_type",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    schedule_run_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("schedule_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relaxation_proposal_id: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    notification_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class ScheduleRecalculationRequest(Base):
    __tablename__ = "schedule_recalculation_requests"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "schedule_run_id",
            "idempotency_key",
            name="uq_schedule_recalculations_run_idempotency_key",
        ),
        CheckConstraint(
            "recalculation_count >= 1 AND recalculation_count <= 3",
            name="ck_schedule_recalculations_count",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    schedule_run_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("schedule_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    recalculation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class SchedulePublication(Base):
    __tablename__ = "schedule_publications"
    __table_args__ = (
        UniqueConstraint(
            "schedule_run_id",
            name="uq_schedule_publications_schedule_run_id",
        ),
        CheckConstraint(
            "status IN ('published', 'archived')",
            name="ck_schedule_publications_status",
        ),
        CheckConstraint(
            "period_start <= period_end",
            name="ck_schedule_publications_period_order",
        ),
        Index(
            "ix_schedule_publications_organization_period",
            "organization_id",
            "period_start",
            "period_end",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    schedule_run_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("schedule_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    assignment_snapshot_hash: Mapped[str] = mapped_column(Text, nullable=False)
    issue_snapshot_hash: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


def normalize_pair_employee_ids(employee_a_id: str, employee_b_id: str) -> tuple[str, str]:
    if employee_a_id == employee_b_id:
        raise ValueError("Pair constraint cannot reference the same employee twice")
    return tuple(sorted((employee_a_id, employee_b_id)))
