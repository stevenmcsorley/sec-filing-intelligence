"""Queue consumer utilities for download workers."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Any, Protocol, cast

from redis.asyncio import Redis

from app.ingestion.models import DownloadTask


def _serialize_payload(task: DownloadTask) -> str:
    """Serialize a task payload deterministically for queue storage."""
    payload = task.to_payload()
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


@dataclass(slots=True)
class DownloadQueueMessage:
    """Container wrapping a dequeued task with bookkeeping metadata."""

    task: DownloadTask
    payload: str
    accession: str
    token: str


class DownloadQueue(Protocol):
    """Protocol for download worker queues."""

    async def push(self, task: DownloadTask) -> bool:
        """Push a download task onto the queue. Returns False if deduplicated."""

    async def pop(self, timeout: int = 5) -> DownloadQueueMessage | None:
        """Pop a task, waiting up to `timeout` seconds."""

    async def ack(self, message: DownloadQueueMessage) -> None:
        """Acknowledge completion of a task."""

    async def length(self) -> int:
        """Return the current backlog size."""

    async def close(self) -> None:
        """Close the queue and release resources."""


class RedisDownloadQueue(DownloadQueue):
    """Queue implementation backed by Redis with dedupe + visibility timeout."""

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
        visibility_timeout: int = 60,
        requeue_batch_size: int = 50,
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

    async def push(self, task: DownloadTask) -> bool:
        payload = _serialize_payload(task)
        enqueued = await cast(
            Coroutine[Any, Any, int],
            self._redis.eval(
                self._push_script,
                2,
                self._queue_name,
                self._dedupe_key,
                payload,
                task.accession_number,
            ),
        )
        return bool(enqueued)

    async def pop(self, timeout: int = 5) -> DownloadQueueMessage | None:
        await self._requeue_expired()

        payload = await cast(
            Coroutine[Any, Any, str | None],
            self._redis.brpoplpush(
                self._queue_name, self._processing_key, timeout=timeout
            ),
        )
        if payload is None:
            return None

        data = json.loads(payload)
        task = DownloadTask.from_payload(data)
        expiry = time.time() + self._visibility_timeout
        accession = task.accession_number
        token = uuid.uuid4().hex

        pipe = self._redis.pipeline()
        pipe.zadd(self._processing_zset, {token: expiry})
        pipe.hset(self._processing_payload, token, payload)
        pipe.hset(self._processing_token, accession, token)
        await pipe.execute()

        return DownloadQueueMessage(task=task, payload=payload, accession=accession, token=token)

    async def ack(self, message: DownloadQueueMessage) -> None:
        stored_token = await cast(
            Coroutine[Any, Any, str | None],
            self._redis.hget(self._processing_token, message.accession),
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
        pipe.hdel(self._processing_token, message.accession)
        pipe.srem(self._dedupe_key, message.accession)
        pipe.lrem(self._processing_key, 0, message.payload)
        await pipe.execute()

    async def _requeue_expired(self) -> None:
        if self._visibility_timeout <= 0:
            return

        now = time.time()
        expired_tokens = await cast(
            Coroutine[Any, Any, list[str]],
            self._redis.zrangebyscore(
                self._processing_zset,
                "-inf",
                now,
                start=0,
                num=self._requeue_batch_size,
            ),
        )
        if not expired_tokens:
            return

        for token in expired_tokens:
            payload = await cast(
                Coroutine[Any, Any, str | None],
                self._redis.hget(self._processing_payload, token),
            )
            pipe = self._redis.pipeline()
            pipe.zrem(self._processing_zset, token)
            pipe.hdel(self._processing_payload, token)
            if payload is not None:
                data = json.loads(payload)
                accession = data["accession_number"]
                pipe.hdel(self._processing_token, accession)
                pipe.lrem(self._processing_key, 0, payload)
                pipe.lpush(self._queue_name, payload)
            else:
                pipe.hdel(self._processing_token, token)
            await pipe.execute()

    async def length(self) -> int:
        return int(
            await cast(
                Coroutine[Any, Any, int],
                self._redis.llen(self._queue_name),
            )
        )

    async def close(self) -> None:
        await self._redis.close()


class InMemoryDownloadQueue(DownloadQueue):
    """Async in-memory queue for tests."""

    def __init__(self, *, visibility_timeout: int = 60) -> None:
        self._queue: asyncio.Queue[DownloadTask] = asyncio.Queue()
        self._visibility_timeout = visibility_timeout
        self._dedupe: set[str] = set()
        self._processing: dict[str, tuple[str, float, str]] = {}
        self._lock = asyncio.Lock()

    async def push(self, task: DownloadTask) -> bool:
        async with self._lock:
            if task.accession_number in self._dedupe:
                return False
            self._dedupe.add(task.accession_number)
            await self._queue.put(task)
            return True

    async def pop(self, timeout: int = 5) -> DownloadQueueMessage | None:
        await self._requeue_expired()
        try:
            task = await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except TimeoutError:
            return None
        payload = _serialize_payload(task)
        accession = task.accession_number
        expires = time.time() + self._visibility_timeout
        async with self._lock:
            token = uuid.uuid4().hex
            self._processing[accession] = (payload, expires, token)
        return DownloadQueueMessage(task=task, payload=payload, accession=accession, token=token)

    async def ack(self, message: DownloadQueueMessage) -> None:
        async with self._lock:
            stored = self._processing.get(message.accession)
            if stored is None:
                return
            payload, _, token = stored
            if token != message.token or payload != message.payload:
                return
            self._processing.pop(message.accession, None)
            self._dedupe.discard(message.accession)

    async def _requeue_expired(self) -> None:
        if self._visibility_timeout <= 0:
            return
        now = time.time()
        async with self._lock:
            expired = [
                (accession, payload)
                for accession, (payload, expires, _) in list(self._processing.items())
                if expires <= now
            ]
            for accession, payload in expired:
                self._processing.pop(accession, None)
                task_payload = json.loads(payload)
                task = DownloadTask.from_payload(task_payload)
                # Requeue without touching dedupe to avoid duplicates
                self._queue.put_nowait(task)

    async def length(self) -> int:
        return self._queue.qsize()

    async def close(self) -> None:
        async with self._lock:
            self._processing.clear()
            self._dedupe.clear()
        while not self._queue.empty():
            self._queue.get_nowait()
