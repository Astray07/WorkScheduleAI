from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Text
from sqlalchemy import UniqueConstraint
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


def normalize_pair_employee_ids(employee_a_id: str, employee_b_id: str) -> tuple[str, str]:
    if employee_a_id == employee_b_id:
        raise ValueError("Pair constraint cannot reference the same employee twice")
    return tuple(sorted((employee_a_id, employee_b_id)))
