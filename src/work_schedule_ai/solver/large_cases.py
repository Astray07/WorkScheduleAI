from __future__ import annotations

from work_schedule_ai.solver.models import (
    EmployeeInput,
    ScheduleRequirementInput,
    ScheduleSlotInput,
    SolveScheduleRequest,
)


def make_large_schedule_request(
    *,
    employee_count: int,
    day_count: int,
) -> SolveScheduleRequest:
    if employee_count < 2:
        raise ValueError("employee_count must be at least 2")
    if day_count < 1:
        raise ValueError("day_count must be at least 1")

    employees = [
        EmployeeInput(
            id=f"emp_{index:03d}",
            role_ids=(
                frozenset({"role_senior"})
                if index % 2 == 0
                else frozenset({"role_junior"})
            ),
        )
        for index in range(1, employee_count + 1)
    ]
    slots = [
        ScheduleSlotInput(
            id=f"slot_2026_07_{day:02d}_day",
            local_date=f"2026-07-{day:02d}",
        )
        for day in range(1, day_count + 1)
    ]
    requirements = [
        ScheduleRequirementInput(
            id=f"req_{slot.id}_{role_id}",
            slot_id=slot.id,
            role_id=role_id,
            required_count=1,
            unfilled_weight=100,
        )
        for slot in slots
        for role_id in ("role_senior", "role_junior")
    ]
    return SolveScheduleRequest(
        employees=employees,
        slots=slots,
        requirements=requirements,
        blocked_pairs=[],
        timeout_seconds=30,
        random_seed=1,
    )
