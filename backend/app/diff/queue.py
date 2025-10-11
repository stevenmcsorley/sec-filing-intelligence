"""Reliable Redis queue for diff tasks."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Any, Protocol, cast

from redis.asyncio import Redis


def _to_int(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError(f"Expected int-compatible value, got {type(value)!r}")


def _to_optional_int(value: object | None) -> int | None:
    if value is None:
        return None
    return _to_int(value)


@dataclass(slots=True)
class DiffTask:
    """Serialized job referencing current and previous filing sections."""

    job_id: str
    diff_id: int
    current_filing_id: int
    previous_filing_id: int
    current_section_id: int | None
    previous_section_id: int | None
    section_ordinal: int
    section_title: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "diff_id": self.diff_id,
            "current_filing_id": self.current_filing_id,
            "previous_filing_id": self.previous_filing_id,
            "current_section_id": self.current_section_id,
            "previous_section_id": self.previous_section_id,
            "section_ordinal": self.section_ordinal,
            "section_title": self.section_title,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> DiffTask:
        return cls(
            job_id=str(payload["job_id"]),
            diff_id=_to_int(payload["diff_id"]),
            current_filing_id=_to_int(payload["current_filing_id"]),
            previous_filing_id=_to_int(payload["previous_filing_id"]),
            current_section_id=_to_optional_int(payload.get("current_section_id")),
            previous_section_id=_to_optional_int(payload.get("previous_section_id")),
            section_ordinal=_to_int(payload["section_ordinal"]),
            section_title=str(payload["section_title"]),
        )


@dataclass(slots=True)
class DiffQueueMessage:
    """Container representing a dequeued diff task."""

    task: DiffTask
    payload: str
    job_id: str
    token: str


class DiffQueue(Protocol):
    """Protocol describing operations for diff job queues."""

    async def push(self, task: DiffTask) -> bool:
        ...

    async def pop(self, timeout: int = 5) -> DiffQueueMessage | None:
        ...

    async def ack(self, message: DiffQueueMessage) -> None:
        ...

    async def close(self) -> None:
        ...


class RedisDiffQueue(DiffQueue):
    """Redis-backed queue with dedupe and visibility timeout semantics."""

    _DEDUP_SUFFIX = ":dedupe"
    _PROCESSING_SUFFIX = ":processing"
    _PROCESSING_ZSET_SUFFIX = ":processing:zset"
    _PROCESSING_PAYLOAD_SUFFIX = ":processing:payload"
    _PROCESSING_TOKEN_SUFFIX = ":processing:token"

    def __init__(
        self,
        redis: Redis,
        queue_name: str,
        *,
        visibility_timeout: int = 600,
        requeue_batch_size: int = 200,
    ) -> None:
        self._redis = redis
        self._queue_name = queue_name
        self._dedupe_key = f"{queue_name}{self._DEDUP_SUFFIX}"
        self._processing_key = f"{queue_name}{self._PROCESSING_SUFFIX}"
        self._processing_zset = f"{queue_name}{self._PROCESSING_ZSET_SUFFIX}"
        self._processing_payload = f"{queue_name}{self._PROCESSING_PAYLOAD_SUFFIX}"
        self._processing_token = f"{queue_name}{self._PROCESSING_TOKEN_SUFFIX}"
        self._visibility_timeout = visibility_timeout
        self._requeue_batch_size = requeue_batch_size
        self._push_script = """
        if redis.call('sadd', KEYS[2], ARGV[2]) == 1 then
            return redis.call('rpush', KEYS[1], ARGV[1])
        else
            return 0
        end
        """

    async def push(self, task: DiffTask) -> bool:
        payload = json.dumps(task.to_payload(), sort_keys=True, separators=(",", ":"))
        enqueued = await cast(
            Coroutine[Any, Any, int],
            self._redis.eval(
                self._push_script,
                2,
                self._queue_name,
                self._dedupe_key,
                payload,
                task.job_id,
            ),
        )
        return bool(enqueued)

    async def pop(self, timeout: int = 5) -> DiffQueueMessage | None:
        await self._requeue_expired()
        payload = await cast(
            Coroutine[Any, Any, str | None],
            self._redis.brpoplpush(self._queue_name, self._processing_key, timeout=timeout),
        )
        if payload is None:
            return None

        data = json.loads(payload)
        task = DiffTask.from_payload(data)
        token = uuid.uuid4().hex
        expiry = time.time() + self._visibility_timeout

        pipe = self._redis.pipeline()
        pipe.zadd(self._processing_zset, {token: expiry})
        pipe.hset(self._processing_payload, token, payload)
        pipe.hset(self._processing_token, task.job_id, token)
        await pipe.execute()

        return DiffQueueMessage(task=task, payload=payload, job_id=task.job_id, token=token)

    async def ack(self, message: DiffQueueMessage) -> None:
        stored_token = await cast(
            Coroutine[Any, Any, str | None],
            self._redis.hget(self._processing_token, message.job_id),
        )
        if stored_token != message.token:
            return
        stored_payload = await cast(
            Coroutine[Any, Any, str | None],
            self._redis.hget(self._processing_payload, stored_token),
        )
        if stored_payload != message.payload:
            return

        pipe = self._redis.pipeline()
        pipe.hdel(self._processing_payload, stored_token)
        pipe.zrem(self._processing_zset, stored_token)
        pipe.hdel(self._processing_token, message.job_id)
        pipe.srem(self._dedupe_key, message.job_id)
        pipe.lrem(self._processing_key, 0, message.payload)
        await pipe.execute()

    async def _requeue_expired(self) -> None:
        if self._visibility_timeout <= 0 or self._requeue_batch_size <= 0:
            return
        expired = await cast(
            Coroutine[Any, Any, list[tuple[str, float]]],
            self._redis.zpopmin(self._processing_zset, self._requeue_batch_size),
        )
        if not expired:
            return

        for token, _ in expired:
            payload = await cast(
                Coroutine[Any, Any, str | None],
                self._redis.hget(self._processing_payload, token),
            )
            pipe = self._redis.pipeline()
            pipe.hdel(self._processing_payload, token)
            if payload is not None:
                job_data = json.loads(payload)
                job_id = str(job_data.get("job_id"))
                pipe.hdel(self._processing_token, job_id)
                pipe.lrem(self._processing_key, 0, payload)
                pipe.lpush(self._queue_name, payload)
            else:
                pipe.hdel(self._processing_token, token)
            await pipe.execute()

    async def close(self) -> None:
        await self._redis.close()


class InMemoryDiffQueue(DiffQueue):
    """Async in-memory diff queue used in tests."""

    def __init__(self, *, visibility_timeout: int = 600) -> None:
        self._queue: asyncio.Queue[DiffTask] = asyncio.Queue()
        self._dedupe: set[str] = set()
        self._processing: dict[str, tuple[DiffTask, float, str]] = {}
        self._processing_tokens: dict[str, str] = {}
        self._visibility_timeout = visibility_timeout
        self._lock = asyncio.Lock()

    async def push(self, task: DiffTask) -> bool:
        async with self._lock:
            if task.job_id in self._dedupe:
                return False
            self._dedupe.add(task.job_id)
            await self._queue.put(task)
            return True

    async def pop(self, timeout: int = 5) -> DiffQueueMessage | None:
        await self._requeue_expired()
        try:
            task = await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except TimeoutError:
            return None

        payload = json.dumps(task.to_payload(), sort_keys=True)
        token = uuid.uuid4().hex
        expiry = time.time() + self._visibility_timeout
        self._processing[task.job_id] = (task, expiry, token)
        self._processing_tokens[token] = task.job_id
        return DiffQueueMessage(task=task, payload=payload, job_id=task.job_id, token=token)

    async def ack(self, message: DiffQueueMessage) -> None:
        entry = self._processing.pop(message.job_id, None)
        if entry is None:
            return
        _, _, token = entry
        self._processing_tokens.pop(token, None)
        self._dedupe.discard(message.job_id)

    async def _requeue_expired(self) -> None:
        if self._visibility_timeout <= 0:
            return
        now = time.time()
        expired_jobs = [
            job_id for job_id, (_, expiry, _) in list(self._processing.items()) if expiry < now
        ]
        for job_id in expired_jobs:
            task, _, token = self._processing.pop(job_id)
            self._processing_tokens.pop(token, None)
            self._dedupe.discard(job_id)
            await self._queue.put(task)

    async def close(self) -> None:
        self._processing.clear()
        self._processing_tokens.clear()
        self._dedupe.clear()
