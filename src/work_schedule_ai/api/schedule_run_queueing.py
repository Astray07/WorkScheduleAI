from __future__ import annotations

import json

from work_schedule_ai.db.models import ScheduleRun
from work_schedule_ai.worker.queue import enqueue_schedule_run


def enqueue_schedule_run_for_run(
    run: ScheduleRun,
    *,
    organization_id: str,
) -> None:
    enqueue_schedule_run(run.id, organization_id=organization_id)


def reenqueue_queued_schedule_run(
    run: ScheduleRun,
    *,
    organization_id: str,
) -> None:
    if run.status != "queued":
        return
    enqueue_schedule_run_for_run(run, organization_id=organization_id)
    _log_queueing_event(
        "schedule_run_reenqueued",
        organization_id=organization_id,
        schedule_run_id=run.id,
        status=run.status,
    )


def _log_queueing_event(event: str, **fields: object) -> None:
    print(
        json.dumps({"event": event, **fields}, ensure_ascii=False, sort_keys=True),
        flush=True,
    )
