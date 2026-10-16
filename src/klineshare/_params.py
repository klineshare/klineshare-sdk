"""Shared request param helpers."""

from __future__ import annotations

from typing import Any, Dict, Optional

# Covered stock/index/ETF/BJ/convertible/treasury/enterprise kline paths.
# Metals / futures / US / plate etc. do not use this default.
DEFAULT_KLINE_FORMAT = 'raw'


def kline_page_timestamp(timestamp: Optional[int]) -> Optional[int]:
    """
    K 线翻页参数 ``timestamp`` 为**秒**；条内字段 ``timestamp`` 为毫秒。

    若传入毫秒（常见于直接用上一页 bar 的 timestamp），自动换成秒。
    """
    if timestamp is None:
        return None
    ts = int(timestamp)
    # 毫秒级约 1e12+；秒级当前约 1e9
    if ts >= 10**12:
        return ts // 1000
    return ts


def with_kline_format(
    params: Dict[str, Any],
    format: Optional[str] = DEFAULT_KLINE_FORMAT,
) -> Dict[str, Any]:
    """
    Attach wire ``format`` for supported kline endpoints.

    Default is ``raw`` (delimiter string). Pass ``format=None`` to omit and use
    the server default (columnar arrays / JSON bars).
    """
    out = dict(params)
    if format is not None:
        out['format'] = format
    else:
        out.pop('format', None)
    return out
