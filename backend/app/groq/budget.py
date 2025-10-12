from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis

from app.groq.metrics import (
    GROQ_BUDGET_DEFERRED_JOBS_TOTAL,
    GROQ_BUDGET_EXHAUSTIONS_TOTAL,
    GROQ_BUDGET_REMAINING_TOKENS,
    GROQ_BUDGET_USAGE_TOKENS,
)


class BudgetExceededError(RuntimeError):
    """Raised when a budget check fails."""


@dataclass(slots=True, frozen=True)
class BudgetScope:
    """Identifies a unique Groq budgeting scope."""

    service: str
    model: str


class TokenReservation:
    """Handles the lifecycle of a reserved token allocation."""

    __slots__ = ("_manager", "_key", "_scope", "_reserved", "_limit")

    def __init__(
        self,
        manager: TokenBudgetManager,
        key: str,
        scope: BudgetScope,
        reserved: int,
        limit: int,
    ) -> None:
        self._manager = manager
        self._key = key
        self._scope = scope
        self._reserved = reserved
        self._limit = limit

    @property
    def reserved(self) -> int:
        return self._reserved

    @property
    def scope(self) -> BudgetScope:
        return self._scope

    async def commit(self, used: int) -> None:
        await self._manager._finalize(self._key, self._scope, self._reserved, used, self._limit)

    async def release(self) -> None:
        await self._manager._finalize(self._key, self._scope, self._reserved, 0, self._limit)


@dataclass(slots=True)
class GroqBudgetLimiter:
    """High-level interface for reserving Groq tokens."""

    manager: TokenBudgetManager
    scope: BudgetScope
    limit: int
    cooldown_seconds: int

    @property
    def service(self) -> str:
        return self.scope.service

    @property
    def model(self) -> str:
        return self.scope.model

    async def reserve(self, estimate: int) -> TokenReservation:
        amount = max(estimate, 1)
        return await self.manager._reserve(self.scope, amount, self.limit)


class TokenBudgetManager:
    """Coordinates Groq token budgeting and telemetry."""

    def __init__(
        self,
        redis: Redis,
        *,
        prefix: str = "sec:groq:budget",
        cooldown_seconds: int = 60,
    ) -> None:
        self._redis = redis
        self._prefix = prefix
        self._cooldown_seconds = cooldown_seconds

    def limiter(
        self,
        *,
        service: str,
        model: str,
        daily_limit: int | None,
    ) -> GroqBudgetLimiter | None:
        if daily_limit is None or daily_limit <= 0:
            return None
        scope = BudgetScope(service=service, model=model)
        return GroqBudgetLimiter(
            manager=self,
            scope=scope,
            limit=daily_limit,
            cooldown_seconds=self._cooldown_seconds,
        )

    async def _reserve(self, scope: BudgetScope, amount: int, limit: int) -> TokenReservation:
        key = self._key(scope)
        pipe = self._redis.pipeline()
        pipe.incrby(key, amount)
        pipe.ttl(key)
        incr, ttl = await pipe.execute()
        total = int(incr)
        if ttl in (-2, -1):
            await self._redis.expireat(key, self._next_midnight_epoch())
        if total > limit:
            await self._redis.decrby(key, amount)
            GROQ_BUDGET_EXHAUSTIONS_TOTAL.labels(scope.service, scope.model).inc()
            raise BudgetExceededError("Daily Groq token budget exceeded")
        self._update_metrics(scope, total, limit)
        return TokenReservation(self, key, scope, amount, limit)

    async def _finalize(
        self,
        key: str,
        scope: BudgetScope,
        reserved: int,
        used: int,
        limit: int,
    ) -> None:
        used = max(used, 0)
        delta = used - reserved
        if delta == 0:
            total = await self._redis.get(key)
            if total is None:
                total_int = 0
            else:
                total_int = int(total)
            self._update_metrics(scope, total_int, limit)
            return

        if delta < 0:
            new_total = await self._redis.decrby(key, -delta)
        else:
            new_total = await self._redis.incrby(key, delta)
            if new_total > limit:
                GROQ_BUDGET_EXHAUSTIONS_TOTAL.labels(scope.service, scope.model).inc()
        await self._redis.expireat(key, self._next_midnight_epoch())
        self._update_metrics(scope, int(new_total), limit)

    def _update_metrics(self, scope: BudgetScope, total: int, limit: int) -> None:
        remaining = max(limit - total, 0)
        GROQ_BUDGET_USAGE_TOKENS.labels(scope.service, scope.model).set(total)
        GROQ_BUDGET_REMAINING_TOKENS.labels(scope.service, scope.model).set(remaining)

    def _key(self, scope: BudgetScope) -> str:
        today = datetime.now(UTC).strftime("%Y%m%d")
        return f"{self._prefix}:{scope.service}:{scope.model}:{today}"

    def _next_midnight_epoch(self) -> int:
        now = datetime.now(UTC)
        tomorrow = (now + timedelta(days=1)).date()
        midnight = datetime.combine(tomorrow, datetime.min.time(), tzinfo=UTC)
        return int(midnight.timestamp())


def record_budget_deferral(limiter: GroqBudgetLimiter) -> None:
    """Increment telemetry when a job is deferred due to budgeting."""

    GROQ_BUDGET_DEFERRED_JOBS_TOTAL.labels(limiter.service, limiter.model).inc()
