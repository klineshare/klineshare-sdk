"""Quota / volume preflight before HTTP."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from klineshare.errors import KlineShareQuotaError
from klineshare.limits.policy import MAX_KLINE_BATCH_SYMBOLS, PathPolicy, resolve_path_policy
from klineshare.limits.snapshot import LimitsSnapshot

# Daily+ multi-symbol load threshold: n_symbols * count
DEFAULT_KLINE_HEAVY_THRESHOLD = 3000


def _split_symbols(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        out: List[str] = []
        for item in value:
            out.extend(_split_symbols(item))
        return [s for s in out if s]
    text = str(value).strip()
    if not text:
        return []
    for sep in (',', ';'):
        if sep in text:
            return [p.strip() for p in text.split(sep) if p.strip()]
    return [text]


def count_symbols(params: Optional[Dict[str, Any]]) -> int:
    if not params:
        return 0
    for key in ('symbol', 'symbols', 'ks_code'):
        if params.get(key) is not None:
            return len(_split_symbols(params.get(key)))
    return 0


def _max_count_for_period(snap: LimitsSnapshot, period: Any) -> Optional[int]:
    max_count = snap.max_kline_count
    try:
        p = int(period) if period is not None else 86400
    except (TypeError, ValueError):
        p = 86400
    if p < 86400 and snap.max_minute_count:
        if max_count is None:
            return snap.max_minute_count
        return min(max_count, snap.max_minute_count)
    return max_count


def should_split_kline_batch(
    *,
    n_symbols: int,
    period: Any,
    count: Any,
    threshold: int = DEFAULT_KLINE_HEAVY_THRESHOLD,
) -> bool:
    """
    Whether a multi-symbol daily+ kline call is too heavy for one HTTP request.

    Single-symbol never splits. Minute bars (period < 86400) never split here
    (already capped by ``max_minute_count``).
    """
    if n_symbols < 2:
        return False
    try:
        p = int(period) if period is not None else 86400
    except (TypeError, ValueError):
        p = 86400
    if p < 86400:
        return False
    try:
        c = int(count) if count is not None else 0
    except (TypeError, ValueError):
        return False
    return c > 0 and n_symbols * c > int(threshold)


def preflight(
    path: str,
    params: Optional[Dict[str, Any]],
    snap: LimitsSnapshot,
    *,
    clamp_count: bool = True,
    overflow: str = 'error',
    soft: bool = False,
) -> Tuple[Dict[str, Any], PathPolicy, int, List[str]]:
    """
    Validate / reshape params against snapshot.

    Returns ``(params, policy, symbol_count, advice)``.
    When ``soft=True`` (limits advise mode), hard quota violations become advice
    strings instead of raising.
    """
    out: Dict[str, Any] = dict(params or {})
    policy = resolve_path_policy(path)
    advice: List[str] = []

    def _fail(exc: KlineShareQuotaError) -> None:
        if soft:
            advice.append(str(exc))
            return
        raise exc

    # Trial remaining by exact path (and longest prefix in endpoint map)
    remaining = snap.endpoint_remaining.get(policy.path)
    if remaining is None:
        for ep_path, rem in snap.endpoint_remaining.items():
            if policy.path == ep_path or policy.path.startswith(ep_path + '/'):
                remaining = rem
                break
    if remaining is not None and remaining <= 0:
        _fail(
            KlineShareQuotaError(
                f'试用次数已用尽: {policy.path}',
                limit_name='endpoint_remaining',
                limit_value=0,
                got=remaining,
                code=403,
            )
        )

    n_sym = count_symbols(out)

    if policy.kind == 'trend' and n_sym > 1:
        _fail(
            KlineShareQuotaError(
                '分时接口每次仅支持 1 个 symbol',
                limit_name='trend_max_symbols',
                limit_value=1,
                got=n_sym,
                code=400,
            )
        )

    if policy.kind == 'realtime_batch':
        max_sym = snap.max_realtime_symbols
        if max_sym is not None and n_sym > max_sym:
            _fail(
                KlineShareQuotaError(
                    f'单次 symbol 数超过套餐上限 {max_sym}',
                    limit_name='max_realtime_symbols',
                    limit_value=max_sym,
                    got=n_sym,
                    code=400,
                )
            )

    if policy.kind == 'kline':
        if n_sym > MAX_KLINE_BATCH_SYMBOLS:
            _fail(
                KlineShareQuotaError(
                    f'K 线单次最多 {MAX_KLINE_BATCH_SYMBOLS} 个 symbol',
                    limit_name='max_kline_batch_symbols',
                    limit_value=MAX_KLINE_BATCH_SYMBOLS,
                    got=n_sym,
                    code=400,
                )
            )
        adjust = out.get('adjust_type')
        if adjust is not None and snap.adjust_types:
            if str(adjust) not in snap.adjust_types:
                _fail(
                    KlineShareQuotaError(
                        f'复权方式不在套餐内: {adjust}',
                        limit_name='adjust_types',
                        limit_value=snap.adjust_types,
                        got=adjust,
                        code=403,
                    )
                )
        max_count = _max_count_for_period(snap, out.get('period'))
        if max_count is not None and out.get('count') is not None:
            try:
                count = int(out['count'])
            except (TypeError, ValueError):
                count = None
            if count is not None and count > max_count:
                if clamp_count:
                    out['count'] = max_count
                    advice.append(f'count 已裁切为套餐上限 {max_count}')
                else:
                    _fail(
                        KlineShareQuotaError(
                            f'count 超过套餐上限 {max_count}',
                            limit_name='max_kline_count',
                            limit_value=max_count,
                            got=count,
                            code=400,
                        )
                    )

    # Symbol-minute quota: refuse if this single call alone exceeds the cap
    if snap.max_symbols_per_minute is not None and n_sym > snap.max_symbols_per_minute:
        _fail(
            KlineShareQuotaError(
                f'单次 symbol 数超过每分钟品种配额 {snap.max_symbols_per_minute}',
                limit_name='max_symbols_per_minute',
                limit_value=snap.max_symbols_per_minute,
                got=n_sym,
                code=400,
            )
        )

    return out, policy, n_sym, advice
