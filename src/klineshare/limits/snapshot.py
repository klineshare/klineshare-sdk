"""Parse and cache GET /v1/me limit fields."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


def _as_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _rule_from_public(entry: Any) -> Optional[Tuple[int, int]]:
    """
    Convert me ``rate_limit`` / scope ``rate_limit`` to ``(requests, window_seconds)``.

    Public shape (from server ``public_rate_limit``)::

        {"requests": 300, "window_minutes": 1, "requests_per_minute": 300}
    """
    if not isinstance(entry, dict):
        return None
    requests = _as_int(entry.get('requests'))
    if requests is None or requests <= 0:
        rpm = _as_int(entry.get('requests_per_minute'))
        if rpm is None or rpm <= 0:
            return None
        return rpm, 60
    if entry.get('window_seconds') is not None:
        win = _as_int(entry.get('window_seconds')) or 60
        return requests, max(1, win)
    win_m = _as_int(entry.get('window_minutes')) or 1
    return requests, max(1, win_m * 60)


@dataclass
class LimitsSnapshot:
    """Normalized limits derived from ``GET /v1/me``."""

    raw: Dict[str, Any] = field(default_factory=dict)
    fetched_at: float = 0.0

    global_rate: Optional[Tuple[int, int]] = None  # (requests, window_secs)
    scope_rates: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    endpoint_rates: Dict[str, Tuple[int, int]] = field(default_factory=dict)

    max_realtime_symbols: Optional[int] = None
    max_symbols_per_minute: Optional[int] = None
    max_realtime_stream_symbols: Optional[int] = None
    max_kline_count: Optional[int] = None
    max_minute_count: Optional[int] = None
    adjust_types: Optional[List[str]] = None
    max_indicator_specs: Optional[int] = None

    # path → remaining uses for trial endpoints (None = not trial / unknown)
    endpoint_remaining: Dict[str, Optional[int]] = field(default_factory=dict)
    endpoint_access_mode: Dict[str, str] = field(default_factory=dict)

    def age_seconds(self, *, now: Optional[float] = None) -> float:
        ts = time.time() if now is None else now
        if not self.fetched_at:
            return float('inf')
        return max(0.0, ts - self.fetched_at)

    def is_stale(self, ttl: float, *, now: Optional[float] = None) -> bool:
        return self.age_seconds(now=now) >= ttl

    def summary(self) -> Dict[str, Any]:
        return {
            'global_rate': self.global_rate,
            'scope_rates': dict(self.scope_rates),
            'max_realtime_symbols': self.max_realtime_symbols,
            'max_symbols_per_minute': self.max_symbols_per_minute,
            'max_kline_count': self.max_kline_count,
            'max_minute_count': self.max_minute_count,
            'adjust_types': list(self.adjust_types) if self.adjust_types else None,
            'fetched_at': self.fetched_at,
        }


def parse_me_payload(payload: Any, *, fetched_at: Optional[float] = None) -> LimitsSnapshot:
    """Build a ``LimitsSnapshot`` from a /v1/me JSON body (envelope or unwrapped)."""
    if not isinstance(payload, dict):
        return LimitsSnapshot(fetched_at=fetched_at or time.time())

    body = payload
    # tolerate {success, data: {...}} if ever nested
    if 'account' not in body and isinstance(body.get('data'), dict):
        inner = body['data']
        if 'account' in inner or 'scopes' in inner or 'kline' in inner:
            body = inner

    snap = LimitsSnapshot(raw=dict(body), fetched_at=fetched_at or time.time())
    snap.global_rate = _rule_from_public(body.get('rate_limit'))
    if snap.global_rate is None and body.get('rate_limit_per_minute') is not None:
        rpm = _as_int(body.get('rate_limit_per_minute'))
        if rpm and rpm > 0:
            snap.global_rate = (rpm, 60)

    for row in body.get('scopes') or []:
        if not isinstance(row, dict):
            continue
        scope = row.get('scope')
        if not scope:
            continue
        rule = _rule_from_public(row.get('rate_limit')) or _rule_from_public(
            row.get('rate_limit_default')
        )
        if rule is None and row.get('rate_limit_per_minute') is not None:
            rpm = _as_int(row.get('rate_limit_per_minute'))
            if rpm and rpm > 0:
                rule = (rpm, 60)
        if rule is not None:
            snap.scope_rates[str(scope)] = rule

    snap.max_realtime_symbols = _as_int(body.get('max_realtime_symbols'))
    snap.max_symbols_per_minute = _as_int(body.get('max_symbols_per_minute'))
    snap.max_realtime_stream_symbols = _as_int(body.get('max_realtime_stream_symbols'))

    kline = body.get('kline') if isinstance(body.get('kline'), dict) else {}
    snap.max_kline_count = _as_int(kline.get('max_count'))
    snap.max_minute_count = _as_int(kline.get('max_minute_count'))
    adjusts = kline.get('adjust_types')
    if isinstance(adjusts, list):
        snap.adjust_types = [str(x) for x in adjusts]
    snap.max_indicator_specs = _as_int(kline.get('max_indicator_specs'))

    for row in body.get('endpoint_access_status') or []:
        if not isinstance(row, dict):
            continue
        path = row.get('path')
        if not path:
            continue
        path = str(path)
        mode = str(row.get('access_mode') or '')
        snap.endpoint_access_mode[path] = mode
        if mode == 'trial':
            snap.endpoint_remaining[path] = _as_int(row.get('remaining'))
        ep_rule = _rule_from_public(row.get('rate_limit'))
        if ep_rule is not None:
            snap.endpoint_rates[path] = ep_rule

    return snap
