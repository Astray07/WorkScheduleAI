from __future__ import annotations

from collections.abc import Callable
from collections import deque
from dataclasses import dataclass, replace
import json
import os
import uuid
from typing import Protocol

from work_schedule_ai.runtime_config import get_redis_url


DEFAULT_QUEUE_NAME = "work-schedule-ai:schedule-runs"
DEFAULT_PROCESSING_LEASE_SECONDS = 900


@dataclass(frozen=True)
class ScheduleRunJob:
    schedule_run_id: str
    organization_id: str | None = None
    queue_payload: str | None = None


class ScheduleRunQueue(Protocol):
    def enqueue(
        self,
        schedule_run_id: str,
        *,
        organization_id: str | None = None,
    ) -> None:
        ...

    def dequeue(self, timeout_seconds: int = 5) -> ScheduleRunJob | None:
        ...


class InMemoryScheduleRunQueue:
    def __init__(self) -> None:
        self._items: deque[ScheduleRunJob] = deque()

    def enqueue(
        self,
        schedule_run_id: str,
        *,
        organization_id: str | None = None,
    ) -> None:
        self._items.append(
            ScheduleRunJob(
                schedule_run_id=schedule_run_id,
                organization_id=organization_id,
            )
        )

    def dequeue(self, timeout_seconds: int = 5) -> ScheduleRunJob | None:
        if not self._items:
            return None
        return self._items.popleft()


class RedisScheduleRunQueue:
    def __init__(
        self,
        redis_url: str,
        queue_name: str = DEFAULT_QUEUE_NAME,
        processing_lease_seconds: int | None = None,
        worker_id: str | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        from redis import Redis

        self._client = Redis.from_url(redis_url, decode_responses=True)
        self._queue_name = queue_name
        self._processing_queue_name = f"{queue_name}:processing"
        self._processing_lease_hash = f"{queue_name}:processing:leases"
        self._processing_owner_hash = f"{queue_name}:processing:owners"
        self._processing_lease_seconds = (
            processing_lease_seconds
            if processing_lease_seconds is not None
            else int(
                os.environ.get(
                    "WORKSCHEDULEAI_QUEUE_LEASE_SECONDS",
                    str(DEFAULT_PROCESSING_LEASE_SECONDS),
                )
            )
        )
        self._worker_id = worker_id or f"worker_{uuid.uuid4().hex}"
        self._clock = clock or _time_seconds

    def enqueue(
        self,
        schedule_run_id: str,
        *,
        organization_id: str | None = None,
    ) -> None:
        self._client.lpush(
            self._queue_name,
            json.dumps(
                {
                    "job_id": f"job_{uuid.uuid4().hex}",
                    "schedule_run_id": schedule_run_id,
                    "organization_id": organization_id,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
        )

    def dequeue(self, timeout_seconds: int = 5) -> ScheduleRunJob | None:
        payload = self._client.brpoplpush(
            self._queue_name,
            self._processing_queue_name,
            timeout=timeout_seconds,
        )
        if payload is None:
            return None
        self._client.hset(
            self._processing_lease_hash,
            payload,
            str(self._clock()),
        )
        self._client.hset(self._processing_owner_hash, payload, self._worker_id)
        return replace(_job_from_payload(payload), queue_payload=payload)

    def ack(self, job: ScheduleRunJob) -> None:
        if job.queue_payload is None:
            return
        self._client.lrem(self._processing_queue_name, 1, job.queue_payload)
        self._client.hdel(self._processing_lease_hash, job.queue_payload)
        self._client.hdel(self._processing_owner_hash, job.queue_payload)

    def recover_in_progress(self, limit: int = 100) -> int:
        recovered_count = 0
        now = self._clock()
        for payload in self._client.lrange(self._processing_queue_name, 0, -1)[:limit]:
            if not self._is_processing_payload_recoverable(payload, now):
                continue
            removed_count = self._client.lrem(self._processing_queue_name, 1, payload)
            if not removed_count:
                continue
            self._client.hdel(self._processing_lease_hash, payload)
            self._client.hdel(self._processing_owner_hash, payload)
            self._client.rpush(self._queue_name, payload)
            recovered_count += 1
        return recovered_count

    def _is_processing_payload_recoverable(self, payload: str, now: float) -> bool:
        lease_started_at = self._client.hget(self._processing_lease_hash, payload)
        if lease_started_at is None:
            return True
        try:
            lease_age = now - float(lease_started_at)
        except ValueError:
            return True
        return lease_age >= self._processing_lease_seconds


_queue: ScheduleRunQueue | None = None


def get_schedule_run_queue() -> ScheduleRunQueue:
    global _queue
    if _queue is None:
        redis_url = get_redis_url()
        _queue = (
            RedisScheduleRunQueue(redis_url)
            if redis_url
            else InMemoryScheduleRunQueue()
        )
    return _queue


def set_schedule_run_queue(queue: ScheduleRunQueue | None) -> None:
    global _queue
    _queue = queue


def enqueue_schedule_run(
    schedule_run_id: str,
    *,
    organization_id: str | None = None,
) -> None:
    get_schedule_run_queue().enqueue(
        schedule_run_id,
        organization_id=organization_id,
    )


def _job_from_payload(payload: str) -> ScheduleRunJob:
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return ScheduleRunJob(schedule_run_id=payload)
    if not isinstance(parsed, dict):
        return ScheduleRunJob(schedule_run_id=payload)
    schedule_run_id = parsed.get("schedule_run_id")
    organization_id = parsed.get("organization_id")
    if not isinstance(schedule_run_id, str):
        return ScheduleRunJob(schedule_run_id=payload)
    return ScheduleRunJob(
        schedule_run_id=schedule_run_id,
        organization_id=organization_id if isinstance(organization_id, str) else None,
    )


def _time_seconds() -> float:
    import time

    return time.time()
