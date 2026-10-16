"""Extended-market symbols must not be forced to .US."""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import MagicMock

from klineshare import Client
from klineshare.client import set_api_key


class _FakeResp:
    def __init__(self, body: Any = None) -> None:
        self._body = body or {'success': True, 'data': {}}
        self.status_code = 200
        self.headers: Dict[str, str] = {}
        self.text = ''

    def json(self) -> Any:
        return self._body


def test_futures_symbol_passthrough() -> None:
    set_api_key('tg_test')
    session = MagicMock()
    session.headers = {}
    session.get.return_value = _FakeResp()
    pro = Client(
        api_key='tg_test',
        base_url='https://data.klineshare.cn',
        session=session,
        as_dataframe=False,
        limits='off',
    )
    pro.futures_kline(symbol='rb2501', period=86400, count=2)
    assert session.get.call_args.kwargs['params']['symbol'] == 'rb2501'
    pro.metal_kline(symbol='XAUUSD', period=86400, count=1)
    assert session.get.call_args.kwargs['params']['symbol'] == 'XAUUSD'
    pro.global_index_realtime(symbol='DJI')
    assert session.get.call_args.kwargs['params']['symbol'] == 'DJI'
