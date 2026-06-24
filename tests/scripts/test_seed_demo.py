from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from scripts.seed_demo import DEMO_ORGANIZATION_ID, DEMO_RUN_ID, seed_demo
from work_schedule_ai.api.routes.schedule_runs import (
    _artifact_hashes,
    _result_artifacts_for_run,
)
from work_schedule_ai.db.models import (
    Assignment,
    Base,
    Employee,
    EmployeeRole,
    Organization,
    OverrideApproval,
    PairConstraint,
    Role,
    ScheduleInputSnapshot,
    SchedulePublication,
    ScheduleRecalculationRequest,
    ScheduleRun,
    ScheduleIssue,
    ScheduleRequirement,
    ShiftSlot,
    ShiftRequirement,
    ShiftType,
    Unavailability,
)


def test_seed_demo_is_idempotent(db_session: Session):
    first_summary = seed_demo(db_session)
    second_summary = seed_demo(db_session)

    assert first_summary.organization_id == DEMO_ORGANIZATION_ID
    assert second_summary.organization_id == DEMO_ORGANIZATION_ID
    assert _count(db_session, Organization) == 1
    assert _count(db_session, Role) == 2
    assert _count(db_session, Employee) == 4
    assert _count(db_session, EmployeeRole) == 4
    assert _count(db_session, ShiftType) == 1
    assert _count(db_session, ShiftRequirement) == 2
    assert _count(db_session, Unavailability) == 1
    assert _count(db_session, PairConstraint) == 1
    assert _count(db_session, ScheduleRun) == 1
    assert _count(db_session, ScheduleInputSnapshot) == 1
    assert _count(db_session, OverrideApproval) == 1
    assert _count(db_session, ScheduleRecalculationRequest) == 1
    assert _count(db_session, SchedulePublication) == 1
    assert _count(db_session, ShiftSlot) == 7
    assert _count(db_session, ScheduleRequirement) == 14
    assert _count(db_session, Assignment) == 14
    assert _count(db_session, ScheduleIssue) == 0


def test_seed_demo_publication_hashes_match_generated_artifacts(db_session: Session):
    seed_demo(db_session)
    run = db_session.get(ScheduleRun, DEMO_RUN_ID)
    publication = db_session.execute(select(SchedulePublication)).scalar_one()
    artifacts = _result_artifacts_for_run(run, db_session)
    hashes = _artifact_hashes(artifacts)

    assert run.recalculation_count == 1
    assert artifacts.issues == []
    assert len(artifacts.assignments) == 14
    assert publication.status == "published"
    assert publication.assignment_snapshot_hash == hashes.assignment_snapshot_hash
    assert publication.issue_snapshot_hash == hashes.issue_snapshot_hash


def _count(db_session: Session, model: type[Base]) -> int:
    return len(db_session.execute(select(model)).scalars().all())


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
