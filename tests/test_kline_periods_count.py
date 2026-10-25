"""Kline period matrix + count length / clamp tests."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from klineshare import Client
from klineshare.client import set_api_key
from klineshare.limits.quota import preflight
from klineshare.limits.snapshot import parse_me_payload

# Documented period seconds (periods_label: 1/5/15/30/60 分、日、周、月)
PERIODS = (60, 300, 900, 1800, 3600, 86400, 604800, 2592000)


class _FakeResp:
    def __init__(self, body: Any) -> None:
        self._body = body
        self.status_code = 200
        self.headers: Dict[str, str] = {}
        self.text = ''

    def json(self) -> Any:
        return self._body


def _me(*, max_count: int = 2000, max_minute: int = 240) -> dict:
    return {
        'account': {},
        'rate_limit': {'requests': 300, 'window_minutes': 1},
        'kline': {
            'max_count': max_count,
            'max_minute_count': max_minute,
            'adjust_types': ['forward', 'backward', 'none'],
        },
        'max_realtime_symbols': 50,
        'scopes': {},
    }


def _client(session: MagicMock, *, limits: str = 'off') -> Client:
    set_api_key('tg_test')
    return Client(
        api_key='tg_test',
        base_url='https://data.klineshare.cn',
        session=session,
        as_dataframe=False,
        limits=limits,
        on_rate_limit='error',
    )


@pytest.mark.parametrize('period', PERIODS)
def test_kline_sends_each_period(period: int) -> None:
    session = MagicMock()
    session.headers = {}
    session.get.return_value = _FakeResp({
        'success': True,
        'fields': ['date', 'timestamp', 'close'],
        'meta': {'period': period},
        'symbols': {'600519.SS': [['20250102', 1_700_000_000_000, 1.0]]},
    })
    pro = _client(session)
    rows = pro.kline(symbol='600519.SS', period=period, count=1, adjust_type='none')
    assert session.get.call_args.kwargs['params']['period'] == period
    assert len(rows) == 1


@pytest.mark.parametrize('count', [1, 10, 100, 240, 2000])
def test_kline_sends_count_as_requested(count: int) -> None:
    session = MagicMock()
    session.headers = {}
    # return exactly `count` bars so caller can assert length if desired
    bars = [[f'202501{i:02d}', 1_700_000_000_000 + i, float(i)] for i in range(1, count + 1)]
    # keep response small for large counts in mock — only check request param
    session.get.return_value = _FakeResp({
        'success': True,
        'fields': ['date', 'timestamp', 'close'],
        'symbols': {'600519.SS': bars[: min(3, count)]},
    })
    pro = _client(session)
    pro.kline(symbol='600519.SS', period=86400, count=count, adjust_type='none')
    assert session.get.call_args.kwargs['params']['count'] == count


def test_preflight_clamps_daily_count_to_max_count() -> None:
    snap = parse_me_payload(_me(max_count=2000, max_minute=240))
    params, _, _, _ = preflight(
        '/v2/kline',
        {'symbol': '600519.SS', 'period': 86400, 'count': 2001},
        snap,
        clamp_count=True,
    )
    assert params['count'] == 2000


def test_preflight_clamps_minute_count_to_max_minute_count() -> None:
    snap = parse_me_payload(_me(max_count=2000, max_minute=240))
    for period in (60, 300, 900, 1800, 3600):
        params, _, _, _ = preflight(
            '/v2/kline',
            {'symbol': '600519.SS', 'period': period, 'count': 241},
            snap,
            clamp_count=True,
        )
        assert params['count'] == 240, f'period={period}'


def test_client_enforce_clamps_minute_and_daily() -> None:
    session = MagicMock()
    session.headers = {}
    me = _me()

    def _side(url, **kwargs):
        if str(url).endswith('/v1/me'):
            return _FakeResp(me)
        return _FakeResp({
            'success': True,
            'fields': ['close'],
            'symbols': {'600519.SS': [[1.0]]},
        })

    session.get.side_effect = _side
    pro = _client(session, limits='enforce')
    pro.kline(symbol='600519.SS', period=60, count=999)
    assert session.get.call_args.kwargs['params']['count'] == 240
    pro.kline(symbol='600519.SS', period=86400, count=9999)
    assert session.get.call_args.kwargs['params']['count'] == 2000


# ----- live -----
def _live_pro() -> Optional[Client]:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    for path in (os.path.join(root, '.env'),):
        if os.path.isfile(path):
            with open(path, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    k, _, v = line.partition('=')
                    k, v = k.strip(), v.strip().strip("'").strip('"')
                    if k and k not in os.environ:
                        os.environ[k] = v
    if os.getenv('KLINESHARE_RUN_LIVE', '').strip() not in ('1', 'true', 'yes'):
        return None
    key = (os.getenv('KLINESHARE_API_KEY') or os.getenv('L2_API_KEY') or '').strip()
    if not key:
        return None
    base = (os.getenv('KLINESHARE_BASE_URL') or os.getenv('L2_API_BASE') or '').strip()
    kw: Dict[str, Any] = dict(
        api_key=key, as_dataframe=False, limits='enforce', on_rate_limit='wait',
    )
    if base:
        kw['base_url'] = base
    return Client(**kw)


@pytest.mark.live
@pytest.mark.parametrize('period', PERIODS)
def test_live_kline_each_period(period: int) -> None:
    pro = _live_pro()
    if pro is None:
        pytest.skip('set KLINESHARE_RUN_LIVE=1 and API key')
    rows = pro.kline(symbol='600519.SS', period=period, count=3, adjust_type='forward')
    assert isinstance(rows, list) and len(rows) == 3
    raw = pro.kline(symbol='600519.SS', period=period, count=3, adjust_type='forward', raw=True)
    assert (raw.get('meta') or {}).get('period') == period
    for bar in rows:
        assert 'close' in bar and 'timestamp' in bar
    pro.close()


@pytest.mark.live
@pytest.mark.parametrize(
    'period,count,expect_len',
    [
        (86400, 1, 1),
        (86400, 10, 10),
        (86400, 100, 100),
        (60, 240, 240),       # minute max
        (60, 241, 240),       # clamp
        (86400, 2000, 2000),  # daily max (this plan)
        (86400, 2001, 2000),  # clamp
    ],
)
def test_live_kline_count_lengths(period: int, count: int, expect_len: int) -> None:
    pro = _live_pro()
    if pro is None:
        pytest.skip('set KLINESHARE_RUN_LIVE=1 and API key')
    rows = pro.kline(symbol='600519.SS', period=period, count=count, adjust_type='none')
    assert isinstance(rows, list)
    assert len(rows) == expect_len, f'period={period} count={count} got={len(rows)}'
    pro.close()
