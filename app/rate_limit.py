import time
from collections import defaultdict, deque
from typing import Deque

from fastapi import HTTPException, status


class SlidingWindowRateLimiter:
    def __init__(self, requests_per_minute: int, burst: int) -> None:
        self.requests_per_minute = requests_per_minute
        self.window_seconds = 60
        self.burst = burst
        self._events: dict[str, Deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.time()
        min_allowed_time = now - self.window_seconds
        capacity = self.requests_per_minute + self.burst
        bucket = self._events[key]

        while bucket and bucket[0] < min_allowed_time:
            bucket.popleft()

        if len(bucket) >= capacity:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: {self.requests_per_minute}/minute with burst {self.burst}",
            )

        bucket.append(now)
