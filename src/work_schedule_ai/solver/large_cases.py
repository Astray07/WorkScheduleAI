from __future__ import annotations

from datetime import date, timedelta

from work_schedule_ai.solver.models import (
    AvoidPair,
    BlockedPair,
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


def make_high_constraint_large_schedule_request(
    *,
    employee_count: int,
    day_count: int,
) -> SolveScheduleRequest:
    if employee_count < 20:
        raise ValueError("employee_count must be at least 20")
    if day_count < 7:
        raise ValueError("day_count must be at least 7")

    slots = _high_constraint_slots(day_count)
    final_slot_id = slots[-1].id
    employees = [
        _high_constraint_employee(
            index=index,
            employee_count=employee_count,
            slots=slots,
            final_slot_id=final_slot_id,
        )
        for index in range(1, employee_count + 1)
    ]
    requirements = [
        ScheduleRequirementInput(
            id=f"req_{slot.id}_{role_id}",
            slot_id=slot.id,
            role_id=role_id,
            required_count=2,
            unfilled_weight=250,
        )
        for slot in slots
        for role_id in ("role_senior", "role_junior")
    ]

    return SolveScheduleRequest(
        employees=employees,
        slots=slots,
        requirements=requirements,
        blocked_pairs=_high_constraint_blocked_pairs(employee_count),
        avoid_pairs=_high_constraint_avoid_pairs(employee_count),
        timeout_seconds=20,
        random_seed=7,
        global_max_shifts_per_week=3,
        max_consecutive_shifts=2,
        min_rest_hours=11,
        weekend_shift_limit_per_month=1,
        night_shift_limit_per_month=2,
        fairness_over_target_weight=50_000,
    )


def _high_constraint_slots(day_count: int) -> list[ScheduleSlotInput]:
    first_day = date(2026, 7, 1)
    slots: list[ScheduleSlotInput] = []
    for offset in range(day_count):
        current_day = first_day + timedelta(days=offset)
        is_night = (offset + 1) % 3 == 0
        if is_night:
            starts_at = f"{current_day.isoformat()}T22:00:00+09:00"
            ends_at = f"{(current_day + timedelta(days=1)).isoformat()}T06:00:00+09:00"
        else:
            starts_at = f"{current_day.isoformat()}T09:00:00+09:00"
            ends_at = f"{current_day.isoformat()}T18:00:00+09:00"
        slots.append(
            ScheduleSlotInput(
                id=f"slot_{current_day.isoformat()}",
                local_date=current_day.isoformat(),
                starts_at=starts_at,
                ends_at=ends_at,
                is_weekend=current_day.weekday() >= 5,
                is_night=is_night,
            )
        )
    return slots


def _high_constraint_employee(
    *,
    index: int,
    employee_count: int,
    slots: list[ScheduleSlotInput],
    final_slot_id: str,
) -> EmployeeInput:
    role_id = "role_senior" if index <= employee_count // 2 else "role_junior"
    unavailable_slot_ids = {
        slots[(index * 3 + offset) % len(slots)].id
        for offset in range(0, len(slots), 11)
    }
    if role_id == "role_senior":
        unavailable_slot_ids.add(final_slot_id)
    return EmployeeInput(
        id=f"emp_{index:03d}",
        role_ids=frozenset({role_id}),
        unavailable_slot_ids=frozenset(unavailable_slot_ids),
        max_shifts_per_week=2 if index % 5 == 0 else None,
    )


def _high_constraint_blocked_pairs(employee_count: int) -> list[BlockedPair]:
    pairs: list[BlockedPair] = []
    senior_count = employee_count // 2
    for index in range(2, senior_count, 10):
        pairs.append(BlockedPair(f"emp_{index:03d}", f"emp_{index + 2:03d}"))
    for index in range(senior_count + 1, employee_count - 1, 10):
        pairs.append(BlockedPair(f"emp_{index:03d}", f"emp_{index + 1:03d}"))
    return pairs


def _high_constraint_avoid_pairs(employee_count: int) -> list[AvoidPair]:
    senior_count = employee_count // 2
    return [
        AvoidPair(f"emp_{index:03d}", f"emp_{senior_count + index:03d}", weight=500)
        for index in range(1, min(senior_count, employee_count - senior_count) + 1, 10)
    ]
