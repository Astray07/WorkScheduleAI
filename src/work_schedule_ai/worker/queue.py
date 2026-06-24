from __future__ import annotations

import os
from collections import deque
from dataclasses import dataclass
from typing import Protocol


DEFAULT_QUEUE_NAME = "work-schedule-ai:schedule-runs"


@dataclass(frozen=True)
class ScheduleRunJob:
    schedule_run_id: str


class ScheduleRunQueue(Protocol):
    def enqueue(self, schedule_run_id: str) -> None:
        ...

    def dequeue(self, timeout_seconds: int = 5) -> ScheduleRunJob | None:
        ...


class InMemoryScheduleRunQueue:
    def __init__(self) -> None:
        self._items: deque[str] = deque()

    def enqueue(self, schedule_run_id: str) -> None:
        self._items.append(schedule_run_id)

    def dequeue(self, timeout_seconds: int = 5) -> ScheduleRunJob | None:
        if not self._items:
            return None
        return ScheduleRunJob(schedule_run_id=self._items.popleft())


class RedisScheduleRunQueue:
    def __init__(self, redis_url: str, queue_name: str = DEFAULT_QUEUE_NAME) -> None:
        from redis import Redis

        self._client = Redis.from_url(redis_url, decode_responses=True)
        self._queue_name = queue_name

    def enqueue(self, schedule_run_id: str) -> None:
        self._client.rpush(self._queue_name, schedule_run_id)

    def dequeue(self, timeout_seconds: int = 5) -> ScheduleRunJob | None:
        item = self._client.blpop([self._queue_name], timeout=timeout_seconds)
        if item is None:
            return None
        _, schedule_run_id = item
        return ScheduleRunJob(schedule_run_id=schedule_run_id)


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


def enqueue_schedule_run(schedule_run_id: str) -> None:
    get_schedule_run_queue().enqueue(schedule_run_id)
