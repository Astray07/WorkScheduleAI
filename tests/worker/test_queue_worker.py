from contextlib import nullcontext
from datetime import date
import importlib
import sys
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from work_schedule_ai.db.models import Base, Organization, ScheduleRun
from work_schedule_ai.worker.queue import (
    InMemoryScheduleRunQueue,
    RedisScheduleRunQueue,
    _job_from_payload,
    get_schedule_run_queue,
    set_schedule_run_queue,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as db_session:
        db_session.add(Organization(id="org_1", name="Clinic A", timezone="Asia/Seoul"))
        db_session.commit()
        yield db_session


def test_run_queue_worker_processes_one_job_with_injected_dependencies(
    session: Session,
):
    try:
        queue_worker_module = importlib.import_module(
            "work_schedule_ai.worker.queue_worker"
        )
    except ModuleNotFoundError as exc:
        pytest.fail(f"queue worker module missing: {exc}")

    run = _queued_run()
    queue = InMemoryScheduleRunQueue()
    queue.enqueue(run.id)
    session.add(run)
    session.commit()

    def executor(db_session: Session, schedule_run: ScheduleRun) -> None:
        schedule_run.solver_status = "cp_sat_optimal"
        schedule_run.solution_quality = "optimal"
        db_session.flush()

    processed_count = queue_worker_module.run_queue_worker(
        queue=queue,
        db_session_factory=lambda: nullcontext(session),
        executor=executor,
        max_jobs=1,
        dequeue_timeout_seconds=0,
    )

    assert processed_count == 1
    assert run.status == "succeeded"
    assert run.solver_status == "cp_sat_optimal"


def test_run_queue_worker_returns_zero_when_no_job_is_available(
    session: Session,
):
    try:
        queue_worker_module = importlib.import_module(
            "work_schedule_ai.worker.queue_worker"
        )
    except ModuleNotFoundError as exc:
        pytest.fail(f"queue worker module missing: {exc}")

    processed_count = queue_worker_module.run_queue_worker(
        queue=InMemoryScheduleRunQueue(),
        db_session_factory=lambda: nullcontext(session),
        max_jobs=1,
        dequeue_timeout_seconds=0,
    )

    assert processed_count == 0


def test_redis_schedule_run_queue_round_trips_json_payload_with_organization_id(
    monkeypatch: pytest.MonkeyPatch,
):
    fake_client = _FakeRedisClient()
    monkeypatch.setitem(
        sys.modules,
        "redis",
        SimpleNamespace(Redis=_FakeRedisFactory(fake_client)),
    )
    queue = RedisScheduleRunQueue("redis://localhost:6379/0", queue_name="queue")

    queue.enqueue("run_1", organization_id="org_1")
    job = queue.dequeue(timeout_seconds=0)

    assert job is not None
    assert job.schedule_run_id == "run_1"
    assert job.organization_id == "org_1"
    assert fake_client.processing_items


def test_redis_schedule_run_queue_ack_removes_processing_payload(
    monkeypatch: pytest.MonkeyPatch,
):
    fake_client = _FakeRedisClient()
    monkeypatch.setitem(
        sys.modules,
        "redis",
        SimpleNamespace(Redis=_FakeRedisFactory(fake_client)),
    )
    queue = RedisScheduleRunQueue("redis://localhost:6379/0", queue_name="queue")

    queue.enqueue("run_1", organization_id="org_1")
    job = queue.dequeue(timeout_seconds=0)
    assert job is not None

    queue.ack(job)

    assert fake_client.processing_items == []


def test_redis_schedule_run_queue_recovers_processing_payloads(
    monkeypatch: pytest.MonkeyPatch,
):
    fake_client = _FakeRedisClient()
    monkeypatch.setitem(
        sys.modules,
        "redis",
        SimpleNamespace(Redis=_FakeRedisFactory(fake_client)),
    )
    queue = RedisScheduleRunQueue("redis://localhost:6379/0", queue_name="queue")

    queue.enqueue("run_1", organization_id="org_1")
    job = queue.dequeue(timeout_seconds=0)
    assert job is not None

    assert queue.recover_in_progress() == 1
    recovered = queue.dequeue(timeout_seconds=0)

    assert recovered is not None
    assert recovered.schedule_run_id == "run_1"


def test_schedule_run_queue_requires_redis_in_production(monkeypatch: pytest.MonkeyPatch):
    set_schedule_run_queue(None)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("REDIS_URL", raising=False)

    with pytest.raises(RuntimeError, match="REDIS_URL"):
        get_schedule_run_queue()

    set_schedule_run_queue(None)


def test_schedule_run_job_payload_parser_accepts_legacy_raw_run_id():
    job = _job_from_payload("run_legacy")

    assert job.schedule_run_id == "run_legacy"
    assert job.organization_id is None


class _FakeRedisClient:
    def __init__(self) -> None:
        self.items: list[tuple[str, str]] = []
        self.processing_items: list[tuple[str, str]] = []

    def rpush(self, queue_name: str, payload: str) -> None:
        self.items.append((queue_name, payload))

    def brpoplpush(self, source: str, destination: str, timeout: int):
        del timeout
        if not self.items:
            return None
        queue_name, payload = self.items.pop(0)
        assert queue_name == source
        self.processing_items.append((destination, payload))
        return payload

    def lrem(self, queue_name: str, count: int, payload: str) -> int:
        assert count == 1
        for index, (item_queue, item_payload) in enumerate(self.processing_items):
            if item_queue == queue_name and item_payload == payload:
                del self.processing_items[index]
                return 1
        return 0

    def rpoplpush(self, source: str, destination: str):
        for index in range(len(self.processing_items) - 1, -1, -1):
            queue_name, payload = self.processing_items[index]
            if queue_name != source:
                continue
            del self.processing_items[index]
            self.items.append((destination, payload))
            return payload
        return None


class _FakeRedisFactory:
    def __init__(self, client: _FakeRedisClient) -> None:
        self.client = client

    def from_url(self, redis_url: str, decode_responses: bool) -> _FakeRedisClient:
        assert redis_url == "redis://localhost:6379/0"
        assert decode_responses is True
        return self.client


def _queued_run(status: str = "queued") -> ScheduleRun:
    return ScheduleRun(
        id="run_1",
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
