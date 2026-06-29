from datetime import date

from work_schedule_ai.api import schedule_run_queueing
from work_schedule_ai.db.models import ScheduleRun


def test_reenqueue_queued_schedule_run_enqueues_only_queued_runs(
    monkeypatch,
    capsys,
):
    enqueued: list[tuple[str, str | None]] = []
    monkeypatch.setattr(
        schedule_run_queueing,
        "enqueue_schedule_run",
        lambda run_id, organization_id=None: enqueued.append((run_id, organization_id)),
    )

    schedule_run_queueing.reenqueue_queued_schedule_run(
        _run("run_queued", status="queued"),
        organization_id="org_1",
    )
    schedule_run_queueing.reenqueue_queued_schedule_run(
        _run("run_succeeded", status="succeeded"),
        organization_id="org_1",
    )

    assert enqueued == [("run_queued", "org_1")]
    captured = capsys.readouterr().out
    assert "schedule_run_reenqueued" in captured
    assert "run_queued" in captured
    assert "org_1" in captured


def test_enqueue_schedule_run_for_run_enqueues_run_id_with_organization(
    monkeypatch,
):
    enqueued: list[tuple[str, str | None]] = []
    monkeypatch.setattr(
        schedule_run_queueing,
        "enqueue_schedule_run",
        lambda run_id, organization_id=None: enqueued.append((run_id, organization_id)),
    )

    schedule_run_queueing.enqueue_schedule_run_for_run(
        _run("run_1", status="queued"),
        organization_id="org_1",
    )

    assert enqueued == [("run_1", "org_1")]


def _run(run_id: str, *, status: str) -> ScheduleRun:
    return ScheduleRun(
        id=run_id,
        organization_id="org_1",
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 7),
        template="one_shift_per_day",
        deterministic_mode=True,
        timeout_seconds=30,
        status=status,
        solver_status=None,
        solution_quality="unknown",
        current_attempt_no=1,
        recalculation_count=0,
    )
