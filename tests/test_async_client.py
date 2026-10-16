"""AsyncClient smoke (stdlib asyncio)."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

from klineshare import AsyncClient, async_pro_api
from klineshare.client import set_api_key


class _FakeResp:
    def __init__(self, body: Any) -> None:
        self._body = body
        self.status_code = 200
        self.headers = {}
        self.text = ''

    def json(self) -> Any:
        return self._body


def test_async_client_kline() -> None:
    set_api_key('tg_test')
    session = MagicMock()
    session.headers = {}
    session.get.return_value = _FakeResp({
        'success': True,
        'fields': ['close'],
        'symbols': {'600519.SS': [[1.0]]},
    })
    from klineshare import Client

    sync = Client(
        api_key='tg_test',
        base_url='https://data.klineshare.cn',
        session=session,
        as_dataframe=False,
        limits='off',
    )
    ac = AsyncClient(sync)

    async def _run():
        rows = await ac.kline(symbol='600519.SS', period=86400, count=1)
        assert rows[0]['close'] == 1.0
        await ac.aclose()

    asyncio.run(_run())
    assert callable(async_pro_api)
