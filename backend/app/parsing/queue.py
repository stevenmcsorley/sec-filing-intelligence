"""Parse queue helpers."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable
from typing import Protocol, cast

from redis.asyncio import Redis

from app.ingestion.models import ParseTask


class ParseQueue(Protocol):
    async def push(self, task: ParseTask) -> None:
        ...

    async def pop(self, timeout: int = 5) -> ParseTask | None:
        ...

    async def close(self) -> None:
        ...


class RedisParseQueue:
    def __init__(self, redis: Redis, queue_name: str) -> None:
        self._redis = redis
        self._queue_name = queue_name

    async def push(self, task: ParseTask) -> None:
        payload = json.dumps(task.to_payload())
        result = self._redis.rpush(self._queue_name, payload)
        if isinstance(result, Awaitable):
            await result

    async def pop(self, timeout: int = 5) -> ParseTask | None:
        raw = self._redis.blpop([self._queue_name], timeout=timeout)
        if isinstance(raw, Awaitable):
            result = await cast(Awaitable[list[str] | None], raw)
        else:
            result = cast(list[str] | None, raw)
        if result is None:
            return None
        _, payload = result
        data = json.loads(payload)
        return ParseTask.from_payload(data)

    async def close(self) -> None:
        await self._redis.close()


class InMemoryParseQueue:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[ParseTask] = asyncio.Queue()

    async def push(self, task: ParseTask) -> None:
        await self._queue.put(task)

    async def pop(self, timeout: int = 5) -> ParseTask | None:
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except TimeoutError:
            return None

    async def close(self) -> None:
        while not self._queue.empty():
            self._queue.get_nowait()


class NullParseQueue:
    async def push(self, task: ParseTask) -> None:  # noqa: D401
        return None

    async def pop(self, timeout: int = 5) -> ParseTask | None:  # noqa: D401
        await asyncio.sleep(timeout)
        return None

    async def close(self) -> None:  # noqa: D401
        return None
