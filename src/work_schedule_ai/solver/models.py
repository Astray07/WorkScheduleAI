from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EmployeeInput:
    id: str
    role_ids: frozenset[str]
    unavailable_slot_ids: frozenset[str] = field(default_factory=frozenset)
    max_shifts_per_week: int | None = None


@dataclass(frozen=True)
class ScheduleSlotInput:
    id: str
    local_date: str


@dataclass(frozen=True)
class ScheduleRequirementInput:
    id: str
    slot_id: str
    role_id: str
    required_count: int
    unfilled_weight: int = 100


@dataclass(frozen=True)
class BlockedPair:
    employee_a_id: str
    employee_b_id: str

    def normalized(self) -> tuple[str, str]:
        return tuple(sorted((self.employee_a_id, self.employee_b_id)))


@dataclass(frozen=True)
class SolveScheduleRequest:
    employees: list[EmployeeInput]
    slots: list[ScheduleSlotInput]
    requirements: list[ScheduleRequirementInput]
    blocked_pairs: list[BlockedPair]
    timeout_seconds: int = 30
    random_seed: int = 1


@dataclass(frozen=True)
class ScheduleAssignment:
    slot_id: str
    role_id: str
    employee_id: str
    requirement_id: str


@dataclass(frozen=True)
class SolveScheduleResult:
    status: str
    solver_status: str
    solution_quality: str
    assignments: list[ScheduleAssignment]
    issues: list[dict[str, object]]
