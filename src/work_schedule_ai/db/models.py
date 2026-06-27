from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Text,
)
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
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        CheckConstraint(
            "role IN ('owner', 'admin', 'scheduler', 'viewer', 'employee', 'member')",
            name="ck_memberships_role",
        ),
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


class EmployeeUserLink(Base):
    __tablename__ = "employee_user_links"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "employee_id"],
            ["employees.organization_id", "employees.id"],
            name="fk_employee_user_links_tenant_employee",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "organization_id",
            "employee_id",
            name="uq_employee_user_links_organization_employee",
        ),
        UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_employee_user_links_organization_user",
        ),
        CheckConstraint(
            "status IN ('invited', 'linked', 'disabled')",
            name="ck_employee_user_links_status",
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
    user_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class EmployeeRequest(Base):
    __tablename__ = "employee_requests"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "employee_id"],
            ["employees.organization_id", "employees.id"],
            name="fk_employee_requests_tenant_employee",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "type IN ('vacation', 'unavailable', 'prefer_shift', 'avoid_shift', 'swap', 'open_shift')",
            name="ck_employee_requests_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'canceled')",
            name="ck_employee_requests_status",
        ),
        CheckConstraint(
            "starts_at < ends_at",
            name="ck_employee_requests_time_order",
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
    requested_by_user_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    ends_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    manager_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_user_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    source_unavailability_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("unavailabilities.id", ondelete="SET NULL"),
        nullable=True,
    )
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
        UniqueConstraint(
            "organization_id",
            "id",
            name="uq_employees_organization_id",
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
        ForeignKeyConstraint(
            ["organization_id", "employee_id"],
            ["employees.organization_id", "employees.id"],
            name="fk_unavailabilities_tenant_employee",
            ondelete="CASCADE",
        ),
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
        UniqueConstraint("organization_id", "id", name="uq_roles_organization_id"),
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


class SchedulePolicy(Base):
    __tablename__ = "schedule_policies"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            name="uq_schedule_policies_organization_id",
        ),
        CheckConstraint("min_rest_hours >= 0", name="ck_schedule_policies_min_rest"),
        CheckConstraint(
            "max_consecutive_shifts >= 1",
            name="ck_schedule_policies_max_consecutive",
        ),
        CheckConstraint(
            "max_shifts_per_week >= 1",
            name="ck_schedule_policies_max_weekly",
        ),
        CheckConstraint(
            "weekend_shift_limit_per_month >= 0",
            name="ck_schedule_policies_weekend_limit",
        ),
        CheckConstraint(
            "night_shift_limit_per_month >= 0",
            name="ck_schedule_policies_night_limit",
        ),
        CheckConstraint(
            "default_unfilled_requirement_weight >= 0",
            name="ck_schedule_policies_unfilled_weight",
        ),
        CheckConstraint(
            "weight_workload_imbalance >= 0",
            name="ck_schedule_policies_workload_weight",
        ),
        CheckConstraint(
            "weight_pair_avoid_violation >= 0",
            name="ck_schedule_policies_pair_avoid_weight",
        ),
        CheckConstraint(
            "unfilled_policy IN ('soft_penalty')",
            name="ck_schedule_policies_unfilled_policy",
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
    min_rest_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    max_consecutive_shifts: Mapped[int] = mapped_column(Integer, nullable=False)
    max_shifts_per_week: Mapped[int] = mapped_column(Integer, nullable=False)
    weekend_shift_limit_per_month: Mapped[int] = mapped_column(Integer, nullable=False)
    night_shift_limit_per_month: Mapped[int] = mapped_column(Integer, nullable=False)
    default_unfilled_requirement_weight: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    weight_workload_imbalance: Mapped[int] = mapped_column(Integer, nullable=False)
    weight_pair_avoid_violation: Mapped[int] = mapped_column(Integer, nullable=False)
    unfilled_policy: Mapped[str] = mapped_column(Text, nullable=False)
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


class ShiftType(Base):
    __tablename__ = "shift_types"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "name",
            name="uq_shift_types_organization_name",
        ),
        UniqueConstraint(
            "organization_id",
            "id",
            name="uq_shift_types_organization_id",
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
    active_weekdays: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="0,1,2,3,4,5,6",
    )
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
        ForeignKeyConstraint(
            ["organization_id", "shift_type_id"],
            ["shift_types.organization_id", "shift_types.id"],
            name="fk_shift_requirements_tenant_shift_type",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "role_id"],
            ["roles.organization_id", "roles.id"],
            name="fk_shift_requirements_tenant_role",
            ondelete="CASCADE",
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
        ForeignKeyConstraint(
            ["organization_id", "employee_id"],
            ["employees.organization_id", "employees.id"],
            name="fk_employee_roles_tenant_employee",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "role_id"],
            ["roles.organization_id", "roles.id"],
            name="fk_employee_roles_tenant_role",
            ondelete="CASCADE",
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
        ForeignKeyConstraint(
            ["organization_id", "employee_a_id"],
            ["employees.organization_id", "employees.id"],
            name="fk_pair_constraints_tenant_employee_a",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "employee_b_id"],
            ["employees.organization_id", "employees.id"],
            name="fk_pair_constraints_tenant_employee_b",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "normalized_employee_a_id"],
            ["employees.organization_id", "employees.id"],
            name="fk_pair_constraints_tenant_normalized_employee_a",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "normalized_employee_b_id"],
            ["employees.organization_id", "employees.id"],
            name="fk_pair_constraints_tenant_normalized_employee_b",
            ondelete="CASCADE",
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
            "id",
            name="uq_schedule_runs_organization_id",
        ),
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


class ShiftSlot(Base):
    __tablename__ = "shift_slots"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "id",
            name="uq_shift_slots_organization_id",
        ),
        ForeignKeyConstraint(
            ["organization_id", "schedule_run_id"],
            ["schedule_runs.organization_id", "schedule_runs.id"],
            name="fk_shift_slots_tenant_schedule_run",
            ondelete="CASCADE",
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
    shift_type_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("shift_types.id", ondelete="SET NULL"),
        nullable=True,
    )
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    starts_at: Mapped[str] = mapped_column(Text, nullable=False)
    ends_at: Mapped[str] = mapped_column(Text, nullable=False)
    timezone: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="generated")
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class ScheduleRequirement(Base):
    __tablename__ = "schedule_requirements"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "schedule_run_id"],
            ["schedule_runs.organization_id", "schedule_runs.id"],
            name="fk_schedule_requirements_tenant_schedule_run",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "shift_slot_id"],
            ["shift_slots.organization_id", "shift_slots.id"],
            name="fk_schedule_requirements_tenant_shift_slot",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "role_id"],
            ["roles.organization_id", "roles.id"],
            name="fk_schedule_requirements_tenant_role",
            ondelete="CASCADE",
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
    shift_slot_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("shift_slots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_name: Mapped[str] = mapped_column(Text, nullable=False)
    required_count: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class Assignment(Base):
    __tablename__ = "assignments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "schedule_run_id"],
            ["schedule_runs.organization_id", "schedule_runs.id"],
            name="fk_assignments_tenant_schedule_run",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "shift_slot_id"],
            ["shift_slots.organization_id", "shift_slots.id"],
            name="fk_assignments_tenant_shift_slot",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "role_id"],
            ["roles.organization_id", "roles.id"],
            name="fk_assignments_tenant_role",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "employee_id"],
            ["employees.organization_id", "employees.id"],
            name="fk_assignments_tenant_employee",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "schedule_run_id",
            "shift_slot_id",
            "role_id",
            "employee_id",
            name="uq_assignments_run_slot_role_employee",
        ),
        UniqueConstraint(
            "schedule_run_id",
            "shift_slot_id",
            "employee_id",
            name="uq_assignments_run_slot_employee",
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
    shift_slot_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("shift_slots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employee_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employee_name: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    locked_by_user: Mapped[bool] = mapped_column(Boolean, nullable=False)
    warning_state: Mapped[str] = mapped_column(Text, nullable=False)
    warning_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class ScheduleIssue(Base):
    __tablename__ = "schedule_issues"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "schedule_run_id"],
            ["schedule_runs.organization_id", "schedule_runs.id"],
            name="fk_schedule_issues_tenant_schedule_run",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "shift_slot_id"],
            ["shift_slots.organization_id", "shift_slots.id"],
            name="fk_schedule_issues_tenant_shift_slot",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "role_id"],
            ["roles.organization_id", "roles.id"],
            name="fk_schedule_issues_tenant_role",
            ondelete="CASCADE",
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
    shift_slot_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("shift_slots.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    role_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)
    missing_count: Mapped[int] = mapped_column(Integer, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    reason_code: Mapped[str] = mapped_column(Text, nullable=False)
    display_message: Mapped[str] = mapped_column(Text, nullable=False)
    related_proposal_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class RelaxationProposal(Base):
    __tablename__ = "relaxation_proposals"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "schedule_run_id"],
            ["schedule_runs.organization_id", "schedule_runs.id"],
            name="fk_relaxation_proposals_tenant_schedule_run",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "affected_shift_slot_id"],
            ["shift_slots.organization_id", "shift_slots.id"],
            name="fk_relaxation_proposals_tenant_shift_slot",
            ondelete="CASCADE",
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
    group_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    requires_proposal_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    affected_shift_slot_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("shift_slots.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    display_summary: Mapped[str] = mapped_column(Text, nullable=False)
    impact_preview_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class SolverDiagnosticEvent(Base):
    __tablename__ = "solver_diagnostic_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "schedule_run_id"],
            ["schedule_runs.organization_id", "schedule_runs.id"],
            name="fk_solver_diagnostics_tenant_schedule_run",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "shift_slot_id"],
            ["shift_slots.organization_id", "shift_slots.id"],
            name="fk_solver_diagnostics_tenant_shift_slot",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "role_id"],
            ["roles.organization_id", "roles.id"],
            name="fk_solver_diagnostics_tenant_role",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "employee_id"],
            ["employees.organization_id", "employees.id"],
            name="fk_solver_diagnostics_tenant_employee",
            ondelete="CASCADE",
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
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    shift_slot_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("shift_slots.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    role_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    employee_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    related_employee_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    constraint_type: Mapped[str] = mapped_column(Text, nullable=False)
    constraint_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_target", "target_type", "target_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_user_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False)
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
            "organization_id",
            "id",
            name="uq_schedule_publications_organization_id",
        ),
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
    result_snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True)
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


class PublicationAcknowledgement(Base):
    __tablename__ = "publication_acknowledgements"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "publication_id"],
            ["schedule_publications.organization_id", "schedule_publications.id"],
            name="fk_publication_acknowledgements_tenant_publication",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "employee_id"],
            ["employees.organization_id", "employees.id"],
            name="fk_publication_acknowledgements_tenant_employee",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "organization_id",
            "publication_id",
            "employee_id",
            name="uq_publication_acknowledgements_employee",
        ),
        CheckConstraint(
            "status IN ('pending', 'acknowledged')",
            name="ck_publication_acknowledgements_status",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    publication_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("schedule_publications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employee_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class PublicationNotification(Base):
    __tablename__ = "publication_notifications"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "publication_id"],
            ["schedule_publications.organization_id", "schedule_publications.id"],
            name="fk_publication_notifications_tenant_publication",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "employee_id"],
            ["employees.organization_id", "employees.id"],
            name="fk_publication_notifications_tenant_employee",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "notification_type IN ('published', 'changed')",
            name="ck_publication_notifications_type",
        ),
        CheckConstraint(
            "channel IN ('in_app', 'email', 'slack')",
            name="ck_publication_notifications_channel",
        ),
        CheckConstraint(
            "status IN ('pending_recorded', 'sent', 'failed', 'suppressed')",
            name="ck_publication_notifications_status",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    publication_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("schedule_publications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employee_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    notification_type: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    delivery_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_delivery_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ComplianceWarningOverride(Base):
    __tablename__ = "compliance_warning_overrides"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "schedule_run_id",
            "warning_code",
            "employee_id",
            "slot_id",
            "week_key",
            "snapshot_hash",
            name="uq_compliance_warning_overrides_instance",
        ),
        ForeignKeyConstraint(
            ["organization_id", "schedule_run_id"],
            ["schedule_runs.organization_id", "schedule_runs.id"],
            name="fk_compliance_warning_overrides_tenant_schedule_run",
            ondelete="CASCADE",
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
    warning_code: Mapped[str] = mapped_column(Text, nullable=False)
    employee_id: Mapped[str] = mapped_column(Text, nullable=False, default="")
    slot_id: Mapped[str] = mapped_column(Text, nullable=False, default="")
    week_key: Mapped[str] = mapped_column(Text, nullable=False, default="")
    snapshot_hash: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_user_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class RagDocument(Base):
    __tablename__ = "rag_documents"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "id",
            name="uq_rag_documents_organization_id",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    document_title: Mapped[str] = mapped_column(Text, nullable=False)
    checked_at: Mapped[date] = mapped_column(Date, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class RagDocumentChunk(Base):
    __tablename__ = "rag_document_chunks"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "document_id",
            "chunk_index",
            name="uq_rag_document_chunks_document_index",
        ),
        ForeignKeyConstraint(
            ["organization_id", "document_id"],
            ["rag_documents.organization_id", "rag_documents.id"],
            name="fk_rag_document_chunks_tenant_document",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("rag_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_dimensions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding_vector_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_content_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class RagQueryAudit(Base):
    __tablename__ = "rag_query_audits"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    query_hash: Mapped[str] = mapped_column(Text, nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False)
    safety_notes_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class DemandDriver(Base):
    __tablename__ = "demand_drivers"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "local_date",
            "segment",
            name="uq_demand_drivers_organization_date_segment",
        ),
        CheckConstraint("demand_count >= 0", name="ck_demand_drivers_demand_count"),
        CheckConstraint(
            "required_staff_count >= 0",
            name="ck_demand_drivers_required_staff_count",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    segment: Mapped[str] = mapped_column(Text, nullable=False)
    demand_count: Mapped[int] = mapped_column(Integer, nullable=False)
    required_staff_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class LaborBudget(Base):
    __tablename__ = "labor_budgets"
    __table_args__ = (
        CheckConstraint(
            "period_start <= period_end",
            name="ck_labor_budgets_period_order",
        ),
        CheckConstraint(
            "budget_amount_cents >= 0",
            name="ck_labor_budgets_budget_amount",
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
    budget_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


def normalize_pair_employee_ids(employee_a_id: str, employee_b_id: str) -> tuple[str, str]:
    if employee_a_id == employee_b_id:
        raise ValueError("Pair constraint cannot reference the same employee twice")
    return tuple(sorted((employee_a_id, employee_b_id)))
