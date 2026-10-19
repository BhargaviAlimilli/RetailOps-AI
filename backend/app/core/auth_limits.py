"""Bounded, process-local login protection; reverse proxies need their own shared limits."""

import asyncio
import hashlib
from collections import OrderedDict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from threading import BoundedSemaphore, Lock
from time import monotonic

from fastapi import HTTPException

from app.core.security import verify_password


@dataclass
class Bucket:
    last_seen: float
    attempts: deque[float] = field(default_factory=deque)


class LoginRateLimiter:
    def __init__(
        self,
        *,
        account_limit: int = 10,
        ip_limit: int = 30,
        window_seconds: float = 60,
        max_buckets: int = 10_000,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self.account_limit = account_limit
        self.ip_limit = ip_limit
        self.window_seconds = window_seconds
        self.max_buckets = max_buckets
        self.clock = clock
        self._buckets: OrderedDict[str, Bucket] = OrderedDict()
        self._lock = Lock()

    def allow(self, ip: str, email: str) -> bool:
        now = self.clock()
        cutoff = now - self.window_seconds
        account = hashlib.sha256(email.strip().lower().encode()).hexdigest()
        keys = [("ip:" + ip, self.ip_limit), ("account:" + account, self.account_limit)]
        with self._lock:
            # Access order and last_seen advance together, so cleanup only scans stale entries.
            while self._buckets:
                oldest = next(iter(self._buckets))
                if self._buckets[oldest].last_seen > cutoff:
                    break
                self._buckets.popitem(last=False)
            missing = sum(key not in self._buckets for key, _ in keys)
            if len(self._buckets) + missing > self.max_buckets:
                return False
            allowed = True
            for key, limit in keys:
                bucket = self._buckets.setdefault(key, Bucket(last_seen=now))
                while bucket.attempts and bucket.attempts[0] <= cutoff:
                    bucket.attempts.popleft()
                bucket.last_seen = now
                self._buckets.move_to_end(key)
                if len(bucket.attempts) >= limit:
                    allowed = False
            if allowed:
                for key, _ in keys:
                    self._buckets[key].attempts.append(now)
            return allowed


login_limiter = LoginRateLimiter()
verification_slots = BoundedSemaphore(4)


async def verify_password_bounded(password: str, encoded: str) -> bool:
    if not verification_slots.acquire(blocking=False):
        raise HTTPException(
            429, "Login capacity reached; retry shortly", headers={"Retry-After": "1"}
        )
    try:
        future = asyncio.get_running_loop().run_in_executor(
            None, verify_password, password, encoded
        )
    except BaseException:
        verification_slots.release()
        raise
    # Shield keeps the slot occupied until the worker ends even if its HTTP request disconnects.
    future.add_done_callback(lambda _: verification_slots.release())
    return await asyncio.shield(future)
