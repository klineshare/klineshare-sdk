"""Tests for iter_kline pagination helper."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

from klineshare import Client
from klineshare.client import set_api_key


class _FakeResp:
    def __init__(self, body: Any, status: int = 200) -> None:
        self._body = body
        self.status_code = status
        self.headers: Dict[str, str] = {}
        self.text = ''

    def json(self) -> Any:
        return self._body


def test_iter_kline_pages_backward() -> None:
    set_api_key('tg_test')
    session = MagicMock()
    session.headers = {}

    page1 = {
        'success': True,
        'fields': ['timestamp', 'close'],
        'symbols': {
            '600519.SS': [
                [1_700_000_000_002, 2.0],
                [1_700_000_000_001, 1.0],
            ],
        },
    }
    page2 = {
        'success': True,
        'fields': ['timestamp', 'close'],
        'symbols': {
            '600519.SS': [
                [1_600_000_000_000, 0.5],
            ],
        },
    }
    calls: List[Optional[int]] = []

    def _side_effect(url, **kwargs):
        ts = kwargs.get('params', {}).get('timestamp')
        calls.append(ts)
        if ts is None:
            return _FakeResp(page1)
        return _FakeResp(page2)

    session.get.side_effect = _side_effect
    pro = Client(
        api_key='tg_test',
        base_url='https://data.klineshare.cn',
        session=session,
        as_dataframe=False,
        limits='off',
    )
    pages = list(
        pro.iter_kline(symbol='600519.SS', period=86400, count=2, max_pages=5)
    )
    assert len(pages) == 2
    assert pages[0][0]['close'] == 2.0
    assert pages[1][0]['close'] == 0.5
    # second request uses earliest ms from page1 minus 1, converted to seconds
    assert calls[0] is None
    assert calls[1] == (1_700_000_000_001 - 1) // 1000
