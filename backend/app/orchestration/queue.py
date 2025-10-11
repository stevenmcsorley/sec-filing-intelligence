"""Reliable Redis queue for Groq chunk jobs."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Any, Protocol, cast

from redis.asyncio import Redis

from .planner import ChunkTask


@dataclass(slots=True)
class ChunkQueueMessage:
    """Container representing a dequeued chunk task."""

    task: ChunkTask
    payload: str
    job_id: str
    token: str


class ChunkQueue(Protocol):
    """Protocol for reliable chunk job queues."""

    async def push(self, task: ChunkTask) -> bool:
        """Push a chunk task onto the queue. Returns False if deduplicated."""

    async def pop(self, timeout: int = 5) -> ChunkQueueMessage | None:
        """Pop a chunk task, waiting up to `timeout` seconds."""

    async def ack(self, message: ChunkQueueMessage) -> None:
        """Acknowledge completion of a chunk job."""

    async def length(self) -> int:
        """Return current queue depth."""

    async def close(self) -> None:
        """Close the queue."""


class RedisChunkQueue(ChunkQueue):
    """Redis-backed queue with dedupe + visibility timeouts."""

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
        visibility_timeout: int = 300,
        requeue_batch_size: int = 100,
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

    async def push(self, task: ChunkTask) -> bool:
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

    async def pop(self, timeout: int = 5) -> ChunkQueueMessage | None:
        await self._requeue_expired()
        payload = await cast(
            Coroutine[Any, Any, str | None],
            self._redis.brpoplpush(self._queue_name, self._processing_key, timeout=timeout),
        )
        if payload is None:
            return None

        data = json.loads(payload)
        task = ChunkTask.from_payload(data)
        token = uuid.uuid4().hex
        expiry = time.time() + self._visibility_timeout

        pipe = self._redis.pipeline()
        pipe.zadd(self._processing_zset, {token: expiry})
        pipe.hset(self._processing_payload, token, payload)
        pipe.hset(self._processing_token, task.job_id, token)
        await pipe.execute()

        return ChunkQueueMessage(task=task, payload=payload, job_id=task.job_id, token=token)

    async def ack(self, message: ChunkQueueMessage) -> None:
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
                job_data = json.loads(payload)
                job_id = str(job_data.get("job_id"))
                pipe.hdel(self._processing_token, job_id)
                pipe.lrem(self._processing_key, 0, payload)
                pipe.lpush(self._queue_name, payload)
            else:
                pipe.hdel(self._processing_token, token)
            await pipe.execute()

    async def length(self) -> int:
        return int(await cast(Coroutine[Any, Any, int], self._redis.llen(self._queue_name)))

    async def close(self) -> None:
        await self._redis.close()


class InMemoryChunkQueue(ChunkQueue):
    """Async in-memory queue primarily for tests."""

    def __init__(self, *, visibility_timeout: int = 300) -> None:
        self._queue: asyncio.Queue[ChunkTask] = asyncio.Queue()
        self._visibility_timeout = visibility_timeout
        self._dedupe: set[str] = set()
        self._processing: dict[str, tuple[str, float, str]] = {}
        self._lock = asyncio.Lock()

    async def push(self, task: ChunkTask) -> bool:
        async with self._lock:
            if task.job_id in self._dedupe:
                return False
            self._dedupe.add(task.job_id)
            await self._queue.put(task)
            return True

    async def pop(self, timeout: int = 5) -> ChunkQueueMessage | None:
        await self._requeue_expired()
        try:
            task = await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except TimeoutError:
            return None
        payload = json.dumps(task.to_payload(), sort_keys=True, separators=(",", ":"))
        job_id = task.job_id
        expires = time.time() + self._visibility_timeout
        token = uuid.uuid4().hex
        async with self._lock:
            self._processing[job_id] = (payload, expires, token)
        return ChunkQueueMessage(task=task, payload=payload, job_id=job_id, token=token)

    async def ack(self, message: ChunkQueueMessage) -> None:
        async with self._lock:
            stored = self._processing.get(message.job_id)
            if stored is None:
                return
            payload, _, token = stored
            if token != message.token or payload != message.payload:
                return
            self._processing.pop(message.job_id, None)
            self._dedupe.discard(message.job_id)

    async def _requeue_expired(self) -> None:
        if self._visibility_timeout <= 0:
            return
        now = time.time()
        async with self._lock:
            expired = [
                (job_id, payload)
                for job_id, (payload, expires, _) in list(self._processing.items())
                if expires <= now
            ]
            for job_id, payload in expired:
                self._processing.pop(job_id, None)
                data = json.loads(payload)
                task = ChunkTask.from_payload(data)
                self._queue.put_nowait(task)

    async def length(self) -> int:
        return self._queue.qsize()

    async def close(self) -> None:
        async with self._lock:
            self._processing.clear()
            self._dedupe.clear()
        while not self._queue.empty():
            self._queue.get_nowait()
