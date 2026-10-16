"""Client-side rate / quota enforcement (see docs/DEVELOPMENT.md §4–§5)."""

from __future__ import annotations

from klineshare.limits.policy import resolve_path_policy
from klineshare.limits.quota import (
    DEFAULT_KLINE_HEAVY_THRESHOLD,
    preflight,
    should_split_kline_batch,
)
from klineshare.limits.rate import RateGate
from klineshare.limits.snapshot import LimitsSnapshot, parse_me_payload

__all__ = [
    'DEFAULT_KLINE_HEAVY_THRESHOLD',
    'LimitsSnapshot',
    'RateGate',
    'parse_me_payload',
    'preflight',
    'resolve_path_policy',
    'should_split_kline_batch',
]
