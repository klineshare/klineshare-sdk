"""Track max_symbols_per_minute locally."""

from __future__ import annotations

import threading
import time
from typing import Optional

from klineshare.errors import KlineShareQuotaError


class SymbolMinuteGate:
    """Fixed 60s window counter for symbol volume quota."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._bucket: int = -1
        self._used: int = 0

    @staticmethod
    def _bucket_id(now: float) -> int:
        return int(now) // 60

    def acquire(self, n_symbols: int, *, limit: Optional[int], now: Optional[float] = None) -> None:
        if limit is None or limit <= 0 or n_symbols <= 0:
            return
        with self._lock:
            ts = time.time() if now is None else now
            bucket = self._bucket_id(ts)
            if bucket != self._bucket:
                self._bucket = bucket
                self._used = 0
            if self._used + n_symbols > int(limit):
                rem = max(0, int(limit) - self._used)
                raise KlineShareQuotaError(
                    f'本分钟品种配额不足（剩余 {rem}，本次需要 {n_symbols}）',
                    limit_name='max_symbols_per_minute',
                    limit_value=limit,
                    got=self._used + n_symbols,
                    code=429,
                )
            self._used += n_symbols
