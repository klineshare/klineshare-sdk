"""Unit tests for client-side limits (Phase B)."""

from __future__ import annotations

from typing import Any, Dict, Optional
from unittest.mock import MagicMock

import pytest

from klineshare import Client, KlineShareQuotaError, KlineShareRateLimitError
from klineshare.client import set_api_key
from klineshare.limits.policy import resolve_path_policy
from klineshare.limits.quota import preflight
from klineshare.limits.rate import RateGate
from klineshare.limits.snapshot import parse_me_payload


def _me_payload(**overrides: Any) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        'success': True,
        'account': {'name': 't', 'plan': '基础版'},
        'scopes': [
            {
                'scope': 'kline',
                'name': 'K线',
                'rate_limit': {'requests': 10, 'window_minutes': 1, 'requests_per_minute': 10},
            },
            {
                'scope': 'realtime',
                'name': '实时',
                'rate_limit': {'requests': 5, 'window_minutes': 1, 'requests_per_minute': 5},
            },
        ],
        'kline': {
            'max_count': 100,
            'max_minute_count': 50,
            'adjust_types': ['forward', 'none'],
        },
        'max_realtime_symbols': 3,
        'max_symbols_per_minute': 20,
        'rate_limit': {'requests': 30, 'window_minutes': 1, 'requests_per_minute': 30},
        'endpoint_access_status': [
            {
                'id': 'limit_up',
                'path': '/v1/limit-up',
                'access_mode': 'trial',
                'remaining': 0,
                'max_uses': 2,
            },
        ],
    }
    base.update(overrides)
    return base


class _FakeResp:
    def __init__(
        self,
        body: Any,
        status: int = 200,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self._body = body
        self.status_code = status
        self.headers = headers or {}
        self.text = ''

    def json(self) -> Any:
        return self._body


def test_parse_me_payload():
    snap = parse_me_payload(_me_payload())
    assert snap.global_rate == (30, 60)
    assert snap.scope_rates['kline'] == (10, 60)
    assert snap.max_realtime_symbols == 3
    assert snap.max_kline_count == 100
    assert snap.adjust_types == ['forward', 'none']
    assert snap.endpoint_remaining['/v1/limit-up'] == 0


def test_resolve_path_policy():
    assert resolve_path_policy('/v2/kline').kind == 'kline'
    assert resolve_path_policy('/v2/kline').scope == 'kline'
    assert resolve_path_policy('/v1/realtime').kind == 'realtime_batch'
    assert resolve_path_policy('/v1/trend').kind == 'trend'
    assert resolve_path_policy('/v1/limit-up/ladder').scope == 'limit_up'
    assert resolve_path_policy('/v1/hkstock/realtime').kind == 'realtime_batch'
    assert resolve_path_policy('/v1/hkstock/realtime').scope == 'hkstock_realtime'
    assert resolve_path_policy('/v2/hkstock/kline').kind == 'kline'
    assert resolve_path_policy('/v1/moneyflow/live').scope == 'moneyflow'


def test_preflight_clamps_count():
    snap = parse_me_payload(_me_payload())
    params, _policy, n, _advice = preflight(
        '/v2/kline',
        {'symbol': '600519.SS', 'period': 86400, 'count': 999},
        snap,
        clamp_count=True,
    )
    assert params['count'] == 100
    assert n == 1


def test_preflight_rejects_too_many_realtime_symbols():
    snap = parse_me_payload(_me_payload())
    with pytest.raises(KlineShareQuotaError) as ei:
        preflight(
            '/v1/realtime',
            {'symbol': 'a.SS,b.SS,c.SS,d.SS'},
            snap,
        )
    assert ei.value.limit_name == 'max_realtime_symbols'


def test_preflight_rejects_trend_multi():
    snap = parse_me_payload(_me_payload())
    with pytest.raises(KlineShareQuotaError):
        preflight('/v1/trend', {'symbol': 'a.SS,b.SS'}, snap)


def test_preflight_rejects_kline_batch_over_5():
    snap = parse_me_payload(_me_payload())
    syms = ','.join(f'{i:06d}.SS' for i in range(6))
    with pytest.raises(KlineShareQuotaError) as ei:
        preflight('/v2/kline', {'symbol': syms, 'count': 10}, snap)
    assert ei.value.limit_name == 'max_kline_batch_symbols'


def test_preflight_trial_exhausted():
    snap = parse_me_payload(_me_payload())
    with pytest.raises(KlineShareQuotaError) as ei:
        preflight('/v1/limit-up', {}, snap)
    assert ei.value.limit_name == 'endpoint_remaining'


def test_preflight_bad_adjust():
    snap = parse_me_payload(_me_payload())
    with pytest.raises(KlineShareQuotaError):
        preflight(
            '/v2/kline',
            {'symbol': '600519.SS', 'adjust_type': 'backward', 'count': 10},
            snap,
        )


def test_rate_gate_error_mode():
    gate = RateGate()
    gate.acquire('g', limit=2, window_secs=60, on_limit='error', now=1_000_000.0)
    gate.acquire('g', limit=2, window_secs=60, on_limit='error', now=1_000_000.0)
    with pytest.raises(KlineShareRateLimitError):
        gate.acquire('g', limit=2, window_secs=60, on_limit='error', now=1_000_000.0)


def test_client_enforce_clamps_and_uses_me():
    set_api_key('tg_test')
    session = MagicMock()
    session.headers = {}

    me_body = _me_payload()
    kline_body = {
        'success': True,
        'data': [{'date': '20250102', 'close': 1.0}],
    }

    def _side_effect(url, **kwargs):
        if url.endswith('/v1/me'):
            return _FakeResp(me_body)
        return _FakeResp(kline_body)

    session.get.side_effect = _side_effect
    pro = Client(
        api_key='tg_test',
        base_url='https://data.klineshare.cn',
        session=session,
        as_dataframe=False,
        limits='enforce',
        on_rate_limit='error',
    )
    data = pro.kline(symbol='600519.SS', period=86400, count=999)
    assert data[0]['close'] == 1.0
    # last call is kline with clamped count
    args, kwargs = session.get.call_args
    assert args[0].endswith('/v2/kline')
    assert kwargs['params']['count'] == 100
    assert pro.limits is not None
    assert pro.limits.max_kline_count == 100


def test_client_rejects_realtime_over_quota_without_upstream():
    set_api_key('tg_test')
    session = MagicMock()
    session.headers = {}
    session.get.return_value = _FakeResp(_me_payload())
    pro = Client(
        api_key='tg_test',
        base_url='https://data.klineshare.cn',
        session=session,
        as_dataframe=False,
        limits='enforce',
    )
    with pytest.raises(KlineShareQuotaError):
        pro.realtime(symbol='a.SS,b.SS,c.SS,d.SS')
    # only /v1/me should have been called
    assert session.get.call_count == 1
    assert session.get.call_args.args[0].endswith('/v1/me')


def test_session_keeps_accept_encoding():
    pro = Client(api_key='tg_x', limits='off')
    ae = pro._session.headers.get('Accept-Encoding', '')
    assert 'gzip' in ae.lower()
    pro.close()
