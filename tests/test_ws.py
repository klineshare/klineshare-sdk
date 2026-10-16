"""Tests for WebSocket feed helpers (mocked)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from klineshare import Client, KlineShareQuotaError
from klineshare.client import set_api_key
from klineshare.limits.snapshot import parse_me_payload
from klineshare.ws import WebSocketFeed, build_ws_url, http_to_ws_base


def test_http_to_ws_base():
    assert http_to_ws_base('https://data.klineshare.cn') == 'wss://data.klineshare.cn'
    assert http_to_ws_base('http://localhost:8000/') == 'ws://localhost:8000'


def test_build_ws_url_includes_key_and_symbol():
    url = build_ws_url(
        'https://data.klineshare.cn',
        '/v1/realtime/ws',
        api_key='tg_x',
        query={'symbol': '600519.SS'},
    )
    assert url.startswith('wss://data.klineshare.cn/v1/realtime/ws?')
    assert 'api_key=tg_x' in url
    assert 'symbol=600519.SS' in url


def test_realtime_ws_url_helper():
    set_api_key('tg_test')
    pro = Client(api_key='tg_test', limits='off')
    url = pro.realtime_ws_url(symbol='600519.SH')
    assert '/v1/realtime/ws' in url
    assert '600519.SS' in url


def test_realtime_ws_quota_local():
    set_api_key('tg_test')
    pro = Client(api_key='tg_test', limits='enforce', on_rate_limit='error')
    pro._limits = parse_me_payload({
        'success': True,
        'scopes': [],
        'kline': {},
        'max_realtime_stream_symbols': 2,
    })
    with pytest.raises(KlineShareQuotaError):
        pro.realtime_ws(symbol='a.SS,b.SS,c.SS')


def test_websocket_feed_iter_and_sub():
    set_api_key('tg_test')
    fake_ws = MagicMock()
    fake_ws.recv.side_effect = [
        json.dumps({'type': 'ready', 'symbols': ['600519.SS']}),
        json.dumps({'type': 'tick', 'symbol': '600519.SS', 'c': 1.0}),
        Exception('closed'),
    ]

    with patch('klineshare.ws._require_websocket') as req:
        mod = MagicMock()
        mod.create_connection.return_value = fake_ws
        req.return_value = mod

        feed = WebSocketFeed('wss://example/ws', api_key='tg_test')
        with feed:
            feed.sub(symbols='600519.SS', snapshot=True)
            msgs = []
            for msg in feed:
                msgs.append(msg)
                if msg.get('type') == 'tick':
                    feed.close()
                    break
        assert msgs[0]['type'] == 'ready'
        assert msgs[1]['type'] == 'tick'
        sent = json.loads(fake_ws.send.call_args[0][0])
        assert sent['op'] == 'sub'
        assert sent['symbols'] == ['600519.SS']


def test_websocket_wrong_entry_retries_once():
    set_api_key('tg_test')
    old_ws = MagicMock()
    old_ws.recv.return_value = json.dumps({
        'success': False,
        'type': 'error',
        'code': 403,
        'message': '当前入口不可用 api_base=https://new-node.example',
    })
    new_ws = MagicMock()
    new_ws.recv.side_effect = [
        json.dumps({'type': 'ready'}),
        json.dumps({'type': 'tick', 'c': 1}),
        Exception('closed'),
    ]

    with patch('klineshare.ws._require_websocket') as req:
        mod = MagicMock()
        mod.create_connection.side_effect = [old_ws, new_ws]
        req.return_value = mod

        adopted = {}

        def on_wrong(hinted, msg):
            adopted['base'] = hinted
            return 'wss://new-node.example/v1/realtime/ws?api_key=tg_test'

        feed = WebSocketFeed(
            'wss://old-node.example/v1/realtime/ws?api_key=tg_test',
            api_key='tg_test',
            on_wrong_entry=on_wrong,
        )
        with feed:
            assert feed.url.startswith('wss://new-node.example/')
            assert adopted['base'] == 'https://new-node.example'
            first = next(iter(feed))
            assert first['type'] == 'ready'
        assert mod.create_connection.call_count == 2
