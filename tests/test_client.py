from __future__ import annotations

from typing import Any, Dict, Optional
from unittest.mock import MagicMock

import pytest

from klineshare import Client, KlineShareAuthError, KlineShareError, KlineShareRateLimitError
from klineshare.client import set_api_key


class _FakeResp:
    def __init__(
        self,
        body: Any,
        status: int = 200,
        headers: Optional[Dict[str, str]] = None,
        text: str = '',
    ) -> None:
        self._body = body
        self.status_code = status
        self.headers = headers or {}
        self.text = text or ('' if body is not None else 'err')

    def json(self) -> Any:
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


def _client_with(session: MagicMock) -> Client:
    set_api_key('tg_test')
    return Client(
        api_key='tg_test',
        base_url='https://data.klineshare.cn',
        session=session,
        as_dataframe=False,
        limits='off',
    )


def test_kline_normalizes_sh_and_unwraps() -> None:
    session = MagicMock()
    session.headers = {}
    session.get.return_value = _FakeResp({
        'success': True,
        'fields': ['date', 'timestamp', 'close'],
        'meta': {'symbols': ['600519.SS']},
        'symbols': {
            '600519.SS': [
                ['20250102', 1_735_776_000_000, 1.0],
                ['20250103', 1_735_862_400_000, 1.1],
            ],
        },
    })
    pro = _client_with(session)
    data = pro.kline(symbol='600519.SH', period=86400, count=2)
    assert data[0]['close'] == 1.0
    assert data[0]['symbol'] == '600519.SS'
    args, kwargs = session.get.call_args
    assert args[0] == 'https://data.klineshare.cn/v2/kline'
    assert kwargs['params']['symbol'] == '600519.SS'
    assert kwargs['params']['period'] == 86400


def test_kline_legacy_data_list_still_unwraps() -> None:
    session = MagicMock()
    session.headers = {}
    session.get.return_value = _FakeResp({
        'success': True,
        'data': [
            {'date': '20250102', 'close': 1.0},
            {'date': '20250103', 'close': 1.1},
        ],
    })
    pro = _client_with(session)
    data = pro.kline(symbol='600519.SS', period=86400, count=2)
    assert data[0]['close'] == 1.0


def test_kline_page_timestamp_accepts_ms() -> None:
    session = MagicMock()
    session.headers = {}
    session.get.return_value = _FakeResp({
        'success': True,
        'fields': ['date', 'close'],
        'symbols': {'600519.SS': [['20250102', 1.0]]},
    })
    pro = _client_with(session)
    # bar timestamps are ms; paging param must be sent as seconds
    pro.kline(symbol='600519.SS', period=86400, count=2, timestamp=1784073600000)
    assert session.get.call_args.kwargs['params']['timestamp'] == 1784073600


def test_ks_code_alias() -> None:
    session = MagicMock()
    session.headers = {}
    session.get.return_value = _FakeResp({'success': True, 'data': {'symbol': '600519.SS'}})
    pro = _client_with(session)
    pro.realtime(ks_code='600519.SH')
    assert session.get.call_args.kwargs['params']['symbol'] == '600519.SS'


def test_public_catalog() -> None:
    session = MagicMock()
    session.headers = {}
    session.get.return_value = _FakeResp({'success': True, 'data': {'tiers': []}})
    pro = _client_with(session)
    data = pro.public_catalog()
    assert data == {'tiers': []}
    assert session.get.call_args.args[0].endswith('/public/v1/catalog')


def test_docs_md_text() -> None:
    session = MagicMock()
    session.headers = {}
    resp = MagicMock()
    resp.status_code = 200
    resp.text = '# docs'
    session.get.return_value = resp
    pro = _client_with(session)
    assert pro.docs_md() == '# docs'


def test_abnormal_events_stream() -> None:
    session = MagicMock()
    session.headers = {}
    resp = MagicMock()
    resp.status_code = 200
    resp.iter_lines.return_value = iter([
        'data: {"type":"ready"}',
        '',
        'data: {"type":"event","data":{"symbol":"600519.SS"}}',
        '',
    ])
    session.get.return_value = resp
    pro = _client_with(session)
    events = list(pro.abnormal_events_stream(types='limit_up'))
    assert events[0]['type'] == 'ready'
    assert events[1]['data']['symbol'] == '600519.SS'
    resp.close.assert_called()


def test_get_generic_path() -> None:
    session = MagicMock()
    session.headers = {}
    session.get.return_value = _FakeResp({'success': True, 'data': {'ok': True}})
    pro = _client_with(session)
    assert pro.get('/v1/health', auth=False) == {'ok': True}


def test_compact_auto_expand() -> None:
    session = MagicMock()
    session.headers = {}
    session.get.return_value = _FakeResp({
        'success': True,
        'format': 'compact',
        'fields': ['symbol', 'price'],
        'sep': '|',
        'data': ['600519.SS|100'],
    })
    pro = _client_with(session)
    rows = pro.realtime_v2(symbol='600519.SS')
    assert rows == [{'symbol': '600519.SS', 'price': 100}]


def test_auth_error() -> None:
    session = MagicMock()
    session.headers = {}
    session.get.return_value = _FakeResp(
        {'success': False, 'code': 403, 'message': '无权限'},
        status=403,
    )
    pro = _client_with(session)
    with pytest.raises(KlineShareAuthError):
        pro.me()


def test_rate_limit() -> None:
    session = MagicMock()
    session.headers = {}
    session.get.return_value = _FakeResp(
        {'success': False, 'code': 429, 'message': 'too many', 'retry_after': 2},
        status=429,
        headers={'Retry-After': '2'},
    )
    pro = _client_with(session)
    with pytest.raises(KlineShareRateLimitError) as ei:
        pro.realtime(symbol='600519.SS')
    assert ei.value.retry_after == 2.0


def test_missing_api_key() -> None:
    set_api_key('')
    pro = Client(api_key='', base_url='https://data.klineshare.cn', as_dataframe=False)
    with pytest.raises(KlineShareAuthError):
        pro.kline(symbol='600519.SS')


def test_raw_envelope() -> None:
    session = MagicMock()
    session.headers = {}
    body = {'success': True, 'data': {'ok': 1}, 'meta': {'x': 1}}
    session.get.return_value = _FakeResp(body)
    pro = _client_with(session)
    assert pro.health(raw=True) == body


def test_api_error_message() -> None:
    session = MagicMock()
    session.headers = {}
    session.get.return_value = _FakeResp(
        {'success': False, 'code': 400, 'message': 'symbol 无效'},
        status=400,
    )
    pro = _client_with(session)
    with pytest.raises(KlineShareError) as ei:
        pro.kline(symbol='600519.SS')
    assert '无效' in str(ei.value)
