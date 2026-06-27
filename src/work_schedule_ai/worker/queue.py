from __future__ import annotations

import os
from collections import deque
from dataclasses import dataclass
import json
from typing import Protocol


DEFAULT_QUEUE_NAME = "work-schedule-ai:schedule-runs"


@dataclass(frozen=True)
class ScheduleRunJob:
    schedule_run_id: str
    organization_id: str | None = None


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
    def __init__(self, redis_url: str, queue_name: str = DEFAULT_QUEUE_NAME) -> None:
        from redis import Redis

        self._client = Redis.from_url(redis_url, decode_responses=True)
        self._queue_name = queue_name

    def enqueue(
        self,
        schedule_run_id: str,
        *,
        organization_id: str | None = None,
    ) -> None:
        self._client.rpush(
            self._queue_name,
            json.dumps(
                {
                    "schedule_run_id": schedule_run_id,
                    "organization_id": organization_id,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
        )

    def dequeue(self, timeout_seconds: int = 5) -> ScheduleRunJob | None:
        item = self._client.blpop([self._queue_name], timeout=timeout_seconds)
        if item is None:
            return None
        _, payload = item
        return _job_from_payload(payload)


_queue: ScheduleRunQueue | None = None


def get_schedule_run_queue() -> ScheduleRunQueue:
    global _queue
    if _queue is None:
        redis_url = os.environ.get("REDIS_URL")
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
