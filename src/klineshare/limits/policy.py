"""Map request paths to scopes and quota rule kinds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

# path → scope for client preflight (aliases included). Authoritative scopes come from /v1/me.
_PATH_SCOPE: Dict[str, str] = {
    '/v1/realtime': 'realtime',
    '/v2/realtime': 'realtime_v2',
    '/v1/auction': 'auction',
    '/v2/auction': 'auction_v2',
    '/v2/market-kline': 'market_kline_v2',
    '/v1/trend': 'trend',
    '/v2/kline': 'kline',
    '/v1/adjust-factors': 'kline',
    '/v1/exrights': 'kline',
    '/v1/adjust-params': 'kline',
    '/v1/bj/trend': 'trend',
    '/v1/bj/kline': 'kline',
    '/v1/bond/kline': 'bond_kline',
    '/v1/bond/realtime': 'bond_realtime',
    '/v1/bond/trend': 'bond_trend',
    '/v1/stock': 'stock',
    '/v1/stocks': 'stock',
    '/v1/corp': 'corp',
    '/v1/finance/report': 'finance',
    '/v1/calendar': 'calendar',
    '/v1/index/realtime': 'index_realtime',
    '/v1/index/trend': 'index_trend',
    '/v2/index/kline': 'index_kline',
    '/v1/etf': 'etf',
    '/v1/etfs': 'etf',
    '/v1/etf/realtime': 'etf_realtime',
    '/v1/etf/trend': 'etf_trend',
    '/v2/etf/kline': 'etf_kline',
    '/v1/limit-up': 'limit_up',
    '/v1/abnormal-events': 'abnormal_events',
    '/v1/market-flash/stream': 'market_flash',
    '/v1/lhb': 'lhb',
    '/v1/hot-money': 'hot_money',
    '/v1/moneyflow': 'moneyflow',
    '/v1/moneyflow/live': 'moneyflow',
    '/v1/moneyflow/ranking/live/stocks': 'moneyflow',
    '/v1/suspend': 'suspend',
    '/v1/zfpg': 'zfpg',
    '/v1/yjfp': 'yjfp',
    '/v1/catalog': 'catalog',
    '/v1/bond': 'bond',
    '/v1/bonds': 'bond',
    '/v1/convertible': 'bond',
    '/v1/convertible/auction': 'auction',
    '/v1/convertible/realtime': 'bond_realtime',
    '/v1/convertible/trend': 'bond_trend',
    '/v2/convertible/kline': 'convertible_kline',
    '/v2/convertible/auction': 'auction_v2',
    '/v1/treasury': 'bond',
    '/v1/treasury/realtime': 'bond_realtime',
    '/v1/treasury/trend': 'bond_trend',
    '/v1/treasury/kline': 'bond_kline',
    '/v1/enterprise': 'bond',
    '/v1/enterprise/realtime': 'bond_realtime',
    '/v1/enterprise/trend': 'bond_trend',
    '/v1/enterprise/kline': 'bond_kline',
    '/v1/metal/realtime': 'metal_realtime',
    '/v2/metal/kline': 'metal_kline',
    '/v1/futures/realtime': 'futures_realtime',
    '/v2/futures/kline': 'futures_kline',
    '/v1/futures/stream': 'futures_stream',
    '/v1/futures-v2/realtime': 'futures_v2_realtime',
    '/v1/futures-v2/trend': 'futures_v2_trend',
    '/v2/futures-v2/kline': 'futures_v2_kline',
    '/v1/futures-v2/stream': 'futures_v2_stream',
    '/v1/global-index/realtime': 'global_index_realtime',
    '/v1/global-index/trend': 'global_index_trend',
    '/v2/global-index/kline': 'global_index_kline',
    '/v1/global-bond/realtime': 'global_bond_realtime',
    '/v2/global-bond/kline': 'global_bond_kline',
    '/v1/usstock/realtime': 'usstock_realtime',
    '/v1/usstock/trend': 'usstock_trend',
    '/v2/usstock/kline': 'usstock_kline',
    '/v1/hkstock/realtime': 'hkstock_realtime',
    '/v1/hkstock/trend': 'hkstock_trend',
    '/v2/hkstock/kline': 'hkstock_kline',
    '/v1/plate/realtime': 'plate_realtime',
    '/v1/plate/trend': 'plate_trend',
    '/v2/plate/kline': 'plate_kline',
    '/v1/plate/moneyflow': 'plate_moneyflow',
    '/v1/plate/moneyflow/ranking': 'plate_moneyflow',
}

_REALTIME_BATCH_PATHS = frozenset({
    '/v1/realtime',
    '/v1/etf/realtime',
    '/v1/index/realtime',
    '/v1/convertible/realtime',
    '/v1/bond/realtime',
    '/v1/metal/realtime',
    '/v1/futures/realtime',
    '/v1/futures-v2/realtime',
    '/v1/global-index/realtime',
    '/v1/global-bond/realtime',
    '/v1/usstock/realtime',
    '/v1/hkstock/realtime',
    '/v1/plate/realtime',
})

_TREND_PATHS = frozenset({
    '/v1/trend',
    '/v1/bj/trend',
    '/v1/etf/trend',
    '/v1/index/trend',
    '/v1/convertible/trend',
    '/v1/bond/trend',
    '/v1/global-index/trend',
    '/v1/usstock/trend',
    '/v1/hkstock/trend',
    '/v1/plate/trend',
    '/v1/futures-v2/trend',
})

_KLINE_PATHS = frozenset({
    '/v2/kline',
    '/v1/bj/kline',
    '/v2/etf/kline',
    '/v2/index/kline',
    '/v2/convertible/kline',
    '/v1/bond/kline',
    '/v1/treasury/kline',
    '/v1/enterprise/kline',
    '/v2/metal/kline',
    '/v2/futures/kline',
    '/v2/futures-v2/kline',
    '/v2/global-index/kline',
    '/v2/global-bond/kline',
    '/v2/usstock/kline',
    '/v2/hkstock/kline',
    '/v2/plate/kline',
})

MAX_KLINE_BATCH_SYMBOLS = 5


@dataclass(frozen=True)
class PathPolicy:
    path: str
    scope: Optional[str]
    kind: str  # none | realtime_batch | trend | kline | other


def _normalize_path(path: str) -> str:
    p = (path or '').strip()
    if not p.startswith('/'):
        p = '/' + p
    if '?' in p:
        p = p.split('?', 1)[0]
    return p.rstrip('/') or '/'


def _longest_prefix(norm: str) -> Tuple[Optional[str], Optional[str]]:
    best: Optional[Tuple[int, str, str]] = None
    for key, scope in _PATH_SCOPE.items():
        if norm == key or norm.startswith(key + '/'):
            if best is None or len(key) > best[0]:
                best = (len(key), key, scope)
    if best is None:
        return None, None
    return best[1], best[2]


def resolve_path_policy(path: str) -> PathPolicy:
    """Longest-prefix match against known API paths."""
    norm = _normalize_path(path)
    matched, scope = _longest_prefix(norm)
    root = matched or norm

    if root in _REALTIME_BATCH_PATHS or norm in _REALTIME_BATCH_PATHS:
        return PathPolicy(path=norm, scope=scope, kind='realtime_batch')
    if root in _TREND_PATHS or norm in _TREND_PATHS:
        return PathPolicy(path=norm, scope=scope, kind='trend')
    if root in _KLINE_PATHS or norm in _KLINE_PATHS:
        return PathPolicy(path=norm, scope=scope, kind='kline')

    if norm.startswith('/v1/') and norm.rstrip('/').endswith('/realtime'):
        return PathPolicy(path=norm, scope=scope, kind='realtime_batch')
    # Full-market minute K compact — independent scope; not symbol-batch kline quotas.
    if root == '/v2/market-kline' or norm == '/v2/market-kline':
        return PathPolicy(path=norm, scope=scope, kind='other')
    if '/kline' in norm:
        return PathPolicy(path=norm, scope=scope, kind='kline')
    if norm.endswith('/trend'):
        return PathPolicy(path=norm, scope=scope, kind='trend')

    return PathPolicy(path=norm, scope=scope, kind='other')
