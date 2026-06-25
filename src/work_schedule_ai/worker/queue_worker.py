from __future__ import annotations

import json
from contextlib import AbstractContextManager
from collections.abc import Callable

from sqlalchemy.orm import Session

from work_schedule_ai.api.dependencies import SessionLocal
from work_schedule_ai.db.models import ScheduleRun
from work_schedule_ai.version import build_info
from work_schedule_ai.worker.queue import ScheduleRunQueue, get_schedule_run_queue
from work_schedule_ai.worker.schedule_worker import (
    ScheduleRunExecutor,
    process_next_schedule_run,
)

DbSessionFactory = Callable[[], AbstractContextManager[Session]]


def run_queue_worker(
    *,
    queue: ScheduleRunQueue | None = None,
    db_session_factory: DbSessionFactory | None = None,
    executor: ScheduleRunExecutor | None = None,
    max_jobs: int | None = None,
    dequeue_timeout_seconds: int = 5,
) -> int:
    schedule_queue = queue or get_schedule_run_queue()
    session_factory = db_session_factory or SessionLocal
    run_executor = executor or _default_schedule_run_executor
    processed_count = 0

    while max_jobs is None or processed_count < max_jobs:
        processed = process_next_schedule_run(
            queue=schedule_queue,
            db_session_factory=session_factory,
            executor=run_executor,
            dequeue_timeout_seconds=dequeue_timeout_seconds,
        )
        if not processed:
            if max_jobs is not None:
                break
            continue
        processed_count += 1

    return processed_count


def _default_schedule_run_executor(
    db_session: Session,
    schedule_run: ScheduleRun,
) -> None:
    from work_schedule_ai.api.routes.schedule_runs import _execute_schedule_run_artifacts

    _execute_schedule_run_artifacts(db_session, schedule_run)


def main() -> int:
    print(
        "Starting schedule queue worker "
        f"{json.dumps(build_info(), sort_keys=True)}",
        flush=True,
    )
    run_queue_worker()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
