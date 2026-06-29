from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from scripts.seed_demo import DEMO_ORGANIZATION_ID
from work_schedule_ai.api.dependencies import SessionLocal, set_tenant_context
from work_schedule_ai.db.models import ScheduleRun
from work_schedule_ai.worker.queue import enqueue_schedule_run


@dataclass(frozen=True)
class RequeueSummary:
    organization_id: str
    requeued_count: int
    run_ids: list[str]


def requeue_queued_schedule_runs(db_session: Session) -> RequeueSummary:
    organization_id = os.environ.get(
        "WORKSCHEDULEAI_REQUEUE_ORGANIZATION_ID",
        DEMO_ORGANIZATION_ID,
    )
    limit = int(os.environ.get("WORKSCHEDULEAI_REQUEUE_LIMIT", "20"))
    set_tenant_context(db_session, organization_id)
    runs = list(
        db_session.execute(
            select(ScheduleRun)
            .where(
                ScheduleRun.organization_id == organization_id,
                ScheduleRun.status == "queued",
            )
            .order_by(ScheduleRun.created_at.asc(), ScheduleRun.id.asc())
            .limit(limit)
        ).scalars()
    )
    for run in runs:
        enqueue_schedule_run(run.id, organization_id=organization_id)
    return RequeueSummary(
        organization_id=organization_id,
        requeued_count=len(runs),
        run_ids=[run.id for run in runs],
    )


def main() -> None:
    with SessionLocal() as session:
        summary = requeue_queued_schedule_runs(session)
    print(json.dumps(asdict(summary), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
