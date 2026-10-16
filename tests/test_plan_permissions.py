"""Multi-plan / permission matrix (mock + optional live keys).

Env (optional live):
  KLINESHARE_RUN_LIVE=1
  KLINESHARE_API_KEY_FREE / KLINESHARE_API_KEY_PRO
  or L2_API_KEY as a single baseline key
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional
from unittest.mock import MagicMock

import pytest

from klineshare import Client, KlineShareAuthError, KlineShareQuotaError
from klineshare.client import set_api_key
from klineshare.limits.snapshot import parse_me_payload


class _FakeResp:
    def __init__(self, body: Any, status: int = 200) -> None:
        self._body = body
        self.status_code = status
        self.headers: Dict[str, str] = {}
        self.text = ''

    def json(self) -> Any:
        return self._body


def _me_free() -> dict:
    return {
        'account': {'plan': '免费版'},
        'rate_limit': {'requests': 60, 'window_minutes': 1},
        'kline': {
            'max_count': 500,
            'max_minute_count': 120,
            'adjust_types': ['forward', 'none'],
            'plan': '免费版',
        },
        'max_realtime_symbols': 5,
        'max_realtime_stream_symbols': 0,
        'scopes': [],
    }


def _me_pro() -> dict:
    return {
        'account': {'plan': '旗舰版'},
        'rate_limit': {'requests': 300, 'window_minutes': 1},
        'kline': {
            'max_count': 2000,
            'max_minute_count': 240,
            'adjust_types': ['forward', 'backward', 'none'],
            'plan': '旗舰版',
        },
        'max_realtime_symbols': 200,
        'max_realtime_stream_symbols': 50,
        'scopes': [],
    }


def test_parse_free_vs_pro_snapshot() -> None:
    free = parse_me_payload(_me_free())
    pro = parse_me_payload(_me_pro())
    assert free.max_kline_count == 500
    assert free.max_minute_count == 120
    assert free.max_realtime_symbols == 5
    assert pro.max_kline_count == 2000
    assert pro.adjust_types and 'backward' in pro.adjust_types


def test_free_plan_rejects_disallowed_adjust() -> None:
    set_api_key('tg_free')
    session = MagicMock()
    session.headers = {}

    def _side(url, **kwargs):
        if str(url).endswith('/v1/me'):
            return _FakeResp(_me_free())
        return _FakeResp({'success': True, 'data': []})

    session.get.side_effect = _side
    client = Client(
        api_key='tg_free',
        base_url='https://data.klineshare.cn',
        session=session,
        as_dataframe=False,
        limits='enforce',
    )
    with pytest.raises(KlineShareQuotaError) as ei:
        client.kline(symbol='600519.SS', period=86400, count=10, adjust_type='backward')
    assert ei.value.limit_name == 'adjust_types'


def test_free_plan_clamps_count_tighter() -> None:
    set_api_key('tg_free')
    session = MagicMock()
    session.headers = {}

    def _side(url, **kwargs):
        if str(url).endswith('/v1/me'):
            return _FakeResp(_me_free())
        return _FakeResp({
            'success': True,
            'fields': ['close'],
            'symbols': {'600519.SS': [[1.0]]},
        })

    session.get.side_effect = _side
    client = Client(
        api_key='tg_free',
        base_url='https://data.klineshare.cn',
        session=session,
        as_dataframe=False,
        limits='enforce',
    )
    client.kline(symbol='600519.SS', period=86400, count=9999)
    assert session.get.call_args.kwargs['params']['count'] == 500


def test_forbidden_endpoint_maps_to_auth_error() -> None:
    set_api_key('tg_free')
    session = MagicMock()
    session.headers = {}
    session.get.return_value = _FakeResp(
        {'success': False, 'code': 403, 'message': '无 实时行情 权限'},
        status=403,
    )
    client = Client(
        api_key='tg_free',
        base_url='https://data.klineshare.cn',
        session=session,
        as_dataframe=False,
        limits='off',
    )
    with pytest.raises(KlineShareAuthError):
        client.metal_realtime()


def _load_env() -> None:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    for path in (
        os.path.join(root, '.env'),
        os.path.join(os.path.dirname(root), 'klineshare-live', '.env'),
        os.path.join(os.path.dirname(root), 'klineshare-level2', '.env'),
    ):
        if not os.path.isfile(path):
            continue
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, _, v = line.partition('=')
                k, v = k.strip(), v.strip().strip("'").strip('"')
                if k and k not in os.environ:
                    os.environ[k] = v


def _live_client(env_key: str) -> Optional[Client]:
    if os.getenv('KLINESHARE_RUN_LIVE', '').strip() not in ('1', 'true', 'yes'):
        return None
    _load_env()
    key = (os.getenv(env_key) or '').strip()
    if not key:
        return None
    base = (os.getenv('KLINESHARE_BASE_URL') or os.getenv('L2_API_BASE') or '').strip()
    kw: Dict[str, Any] = dict(api_key=key, as_dataframe=False, limits='enforce')
    if base:
        kw['base_url'] = base
    return Client(**kw)


@pytest.mark.live
def test_live_me_plan_fields_present() -> None:
    """Baseline: any available key must expose plan/limit fields via me()."""
    _load_env()
    if os.getenv('KLINESHARE_RUN_LIVE', '').strip() not in ('1', 'true', 'yes'):
        pytest.skip('set KLINESHARE_RUN_LIVE=1')
    key = (
        os.getenv('KLINESHARE_API_KEY_PRO')
        or os.getenv('KLINESHARE_API_KEY')
        or os.getenv('L2_API_KEY')
        or ''
    ).strip()
    if not key:
        pytest.skip('no API key')
    base = (os.getenv('KLINESHARE_BASE_URL') or os.getenv('L2_API_BASE') or '').strip()
    kw: Dict[str, Any] = dict(api_key=key, as_dataframe=False, limits='off')
    if base:
        kw['base_url'] = base
    pro = Client(**kw)
    me = pro.me()
    assert isinstance(me, dict)
    kline = me.get('kline') or {}
    assert kline.get('max_count') is not None
    pro.close()


@pytest.mark.live
def test_live_free_vs_pro_if_both_keys() -> None:
    free = _live_client('KLINESHARE_API_KEY_FREE')
    paid = _live_client('KLINESHARE_API_KEY_PRO')
    if free is None or paid is None:
        pytest.skip('need both KLINESHARE_API_KEY_FREE and KLINESHARE_API_KEY_PRO')
    mf = free.me()
    mp = paid.me()
    cf = (mf.get('kline') or {}).get('max_count')
    cp = (mp.get('kline') or {}).get('max_count')
    assert cf is not None and cp is not None
    # typically pro >= free; if equal, still assert both readable
    assert int(cp) >= int(cf)
    free.close()
    paid.close()
