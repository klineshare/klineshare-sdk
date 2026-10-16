"""Tests for kline batch auto-split, limits=advise, SSE preflight."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from klineshare import Client, KlineShareQuotaError
from klineshare.client import set_api_key
from klineshare.limits.quota import should_split_kline_batch


class _FakeResp:
    def __init__(self, body: Any, status: int = 200) -> None:
        self._body = body
        self.status_code = status
        self.headers: Dict[str, str] = {}
        self.text = ''

    def json(self) -> Any:
        return self._body


def test_should_split_rules() -> None:
    assert not should_split_kline_batch(n_symbols=1, period=86400, count=9999)
    assert not should_split_kline_batch(n_symbols=3, period=60, count=240)
    assert not should_split_kline_batch(n_symbols=3, period=86400, count=500)  # 1500 <= 3000
    assert should_split_kline_batch(n_symbols=3, period=86400, count=1500)  # 4500 > 3000
    assert should_split_kline_batch(n_symbols=2, period=86400, count=2000)  # 4000 > 3000


def test_kline_batch_auto_splits_heavy_daily() -> None:
    set_api_key('tg_test')
    session = MagicMock()
    session.headers = {}
    calls: List[str] = []

    def _side(url, **kwargs):
        sym = kwargs.get('params', {}).get('symbol')
        calls.append(str(sym))
        return _FakeResp({
            'success': True,
            'fields': ['date', 'close'],
            'symbols': {sym: [['20250102', 1.0]]},
        })

    session.get.side_effect = _side
    pro = Client(
        api_key='tg_test',
        base_url='https://data.klineshare.cn',
        session=session,
        as_dataframe=False,
        limits='off',
        kline_batch='auto',
        kline_heavy_threshold=3000,
    )
    rows = pro.kline(
        symbol=['600519.SS', '000001.SZ', '000002.SZ'],
        period=86400,
        count=1500,
    )
    assert len(calls) == 3
    assert set(calls) == {'600519.SS', '000001.SZ', '000002.SZ'}
    assert len(rows) == 3


def test_kline_batch_multi_keeps_one_request() -> None:
    set_api_key('tg_test')
    session = MagicMock()
    session.headers = {}
    session.get.return_value = _FakeResp({
        'success': True,
        'fields': ['date', 'close'],
        'symbols': {
            '600519.SS': [['20250102', 1.0]],
            '000001.SZ': [['20250102', 2.0]],
        },
    })
    pro = Client(
        api_key='tg_test',
        base_url='https://data.klineshare.cn',
        session=session,
        as_dataframe=False,
        limits='off',
        kline_batch='multi',
    )
    rows = pro.kline(symbol=['600519.SS', '000001.SZ'], period=86400, count=1500)
    assert session.get.call_count == 1
    assert len(rows) == 2


def test_limits_advise_does_not_raise_on_quota() -> None:
    set_api_key('tg_test')
    session = MagicMock()
    session.headers = {}
    me = {
        'account': {},
        'rate_limit': {'requests': 30, 'window_minutes': 1},
        'kline': {'max_count': 100, 'adjust_types': ['forward', 'none']},
        'max_realtime_symbols': 2,
        'scopes': [],
        'endpoint_access_status': [
            {
                'path': '/v1/limit-up',
                'access_mode': 'trial',
                'remaining': 0,
                'allowed': False,
            }
        ],
    }

    def _side(url, **kwargs):
        if str(url).endswith('/v1/me'):
            return _FakeResp(me)
        return _FakeResp({'success': True, 'data': {'ok': 1}})

    session.get.side_effect = _side
    pro = Client(
        api_key='tg_test',
        base_url='https://data.klineshare.cn',
        session=session,
        as_dataframe=False,
        limits='advise',
    )
    # would raise under enforce
    pro.realtime(symbol='a.SS,b.SS,c.SS')
    assert any('max_realtime_symbols' in a or '超过套餐' in a for a in pro.limit_advice)


def test_sse_stream_runs_rate_gate() -> None:
    set_api_key('tg_test')
    session = MagicMock()
    session.headers = {}
    me = {
        'account': {},
        'rate_limit': {'requests': 1, 'window_minutes': 1},
        'kline': {'max_count': 100, 'adjust_types': ['forward']},
        'scopes': [{'scope': 'abnormal_events', 'rate_limit': {'requests': 1, 'window_minutes': 1}}],
    }
    n = {'i': 0}

    def _side(url, **kwargs):
        if str(url).endswith('/v1/me'):
            return _FakeResp(me)
        n['i'] += 1
        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {}
        resp.iter_lines.return_value = iter(['data: {"type":"ready"}', ''])
        resp.close = MagicMock()
        return resp

    session.get.side_effect = _side
    pro = Client(
        api_key='tg_test',
        base_url='https://data.klineshare.cn',
        session=session,
        as_dataframe=False,
        limits='enforce',
        on_rate_limit='error',
    )
    list(pro.stream('/v1/abnormal-events/stream'))
    with pytest.raises(Exception):
        # second stream in same window should hit rate gate
        list(pro.stream('/v1/abnormal-events/stream'))
