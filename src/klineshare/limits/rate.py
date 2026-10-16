"""Local fixed-window rate gate (aligned with server minute buckets)."""

from __future__ import annotations

import threading
import time
from typing import Dict, Optional, Tuple

from klineshare.errors import KlineShareRateLimitError


class RateGate:
    """
    Process-local rate limiter.

    Window buckets use ``floor(now / window_secs)``, matching the server's
    fixed-window style (see klineshare ``rate_limit_bucket``).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # key -> (bucket_id, count, window_secs, limit)
        self._windows: Dict[str, Tuple[int, int, int, int]] = {}
        self._block_until: Dict[str, float] = {}

    @staticmethod
    def _bucket(now: float, window_secs: int) -> int:
        return int(now) // max(1, window_secs)

    @staticmethod
    def _retry_after(now: float, window_secs: int) -> float:
        win = max(1, window_secs)
        rem = win - (int(now) % win)
        return float(rem or win)

    def calibrate(self, key: str, *, retry_after: Optional[float] = None) -> None:
        """After a real HTTP 429, block local window until ``retry_after`` elapses."""
        with self._lock:
            now = time.time()
            wait = float(retry_after) if retry_after is not None else self._retry_after(now, 60)
            self._block_until[key] = now + max(0.0, wait)
            state = self._windows.get(key)
            if state is not None:
                bucket, _count, win, limit = state
                self._windows[key] = (bucket, max(limit, 1), win, max(limit, 1))

    def acquire(
        self,
        key: str,
        *,
        limit: Optional[int],
        window_secs: int = 60,
        on_limit: str = 'wait',
        now: Optional[float] = None,
        sleep: bool = True,
    ) -> None:
        """
        Reserve one request in the window for ``key``.

        ``on_limit``: ``wait`` sleeps until the next window; ``error`` raises
        ``KlineShareRateLimitError``.
        """
        if limit is None or limit <= 0:
            return
        win = max(1, int(window_secs))
        while True:
            with self._lock:
                ts = time.time() if now is None else now
                block_until = self._block_until.get(key)
                if block_until is not None and ts < block_until:
                    wait = block_until - ts
                    if on_limit == 'error':
                        raise KlineShareRateLimitError(
                            f'本地限流：{key} 冷却中',
                            code=429,
                            retry_after=wait,
                        )
                    delay = wait
                else:
                    if block_until is not None and ts >= block_until:
                        self._block_until.pop(key, None)
                    bucket = self._bucket(ts, win)
                    state = self._windows.get(key)
                    if state is None or state[0] != bucket or state[2] != win:
                        self._windows[key] = (bucket, 1, win, int(limit))
                        return
                    _b, count, _w, _lim = state
                    if count < int(limit):
                        self._windows[key] = (bucket, count + 1, win, int(limit))
                        return
                    delay = self._retry_after(ts, win)
                    if on_limit == 'error':
                        raise KlineShareRateLimitError(
                            f'本地限流：{key} 超过 {limit} 次/{win}s',
                            code=429,
                            retry_after=delay,
                        )
            if not sleep:
                raise KlineShareRateLimitError(
                    f'本地限流：{key} 超过 {limit} 次/{win}s',
                    code=429,
                    retry_after=delay,
                )
            time.sleep(min(delay, 1.0) if delay > 1 else delay)
            now = None  # refresh clock after sleep
