"""Follow GET /v1/me ``api_base`` as the request root."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from klineshare import Client, KlineShareAuthError
from klineshare._api_base import extract_api_base
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
        self.text = text or ''

    def json(self) -> Any:
        return self._body

    def close(self) -> None:
        return None


def _client(*, follow: bool = True, limits: str = 'off') -> tuple[Client, MagicMock]:
    set_api_key('tg_test')
    session = MagicMock()
    session.headers = {}
    pro = Client(
        api_key='tg_test',
        base_url='https://data.klineshare.cn',
        session=session,
        as_dataframe=False,
        limits=limits,
        follow_api_base=follow,
    )
    return pro, session


def test_me_adopts_api_base() -> None:
    pro, session = _client()
    session.get.return_value = _FakeResp({
        'success': True,
        'account': {'name': 't', 'plan': '专业版'},
        'scopes': [],
        'kline': {},
        'api_base': 'https://market-api.example/',
    })
    pro.me()
    assert pro.api_base == 'https://market-api.example'
    assert pro.base_url == 'https://market-api.example'


def test_follow_api_base_false_keeps_entry() -> None:
    pro, session = _client(follow=False)
    session.get.return_value = _FakeResp({
        'success': True,
        'account': {},
        'scopes': [],
        'kline': {},
        'api_base': 'https://market-api.example',
    })
    pro.me()
    assert pro.api_base == 'https://market-api.example'
    assert pro.base_url == 'https://data.klineshare.cn'


def test_refresh_limits_switches_before_business() -> None:
    pro, session = _client(limits='enforce')

    def _side_effect(url: str, **kwargs: Any) -> _FakeResp:
        if url.endswith('/v1/me'):
            return _FakeResp({
                'success': True,
                'account': {},
                'scopes': [{
                    'scope': 'realtime',
                    'rate_limit': {'requests': 60, 'window_minutes': 1},
                }],
                'kline': {},
                'max_realtime_symbols': 10,
                'api_base': 'https://node-b.example',
            })
        assert url.startswith('https://node-b.example/')
        return _FakeResp({'success': True, 'data': {'symbol': '600519.SS'}})

    session.get.side_effect = _side_effect
    data = pro.realtime(symbol='600519.SS')
    assert data['symbol'] == '600519.SS'
    assert pro.base_url == 'https://node-b.example'
    urls = [c.args[0] for c in session.get.call_args_list]
    assert urls[0] == 'https://data.klineshare.cn/v1/me'
    assert urls[1] == 'https://node-b.example/v1/realtime'


def test_403_with_api_base_retries_once() -> None:
    pro, session = _client(limits='off')
    responses: List[_FakeResp] = [
        _FakeResp(
            {
                'success': False,
                'code': 403,
                'message': '请使用分配的入口：https://node-b.example',
                'api_base': 'https://node-b.example',
            },
            status=403,
        ),
        _FakeResp({'success': True, 'data': {'ok': True}}),
    ]
    session.get.side_effect = responses
    out = pro.realtime(symbol='600519.SS')
    assert out == {'ok': True}
    assert pro.base_url == 'https://node-b.example'
    assert session.get.call_args_list[0].args[0] == 'https://data.klineshare.cn/v1/realtime'
    assert session.get.call_args_list[1].args[0] == 'https://node-b.example/v1/realtime'


def test_403_without_switch_raises_with_api_base() -> None:
    pro, session = _client(follow=False, limits='off')
    session.get.return_value = _FakeResp(
        {
            'success': False,
            'code': 403,
            'message': '当前入口不可用，请改用分配地址请求：https://node-b.example',
            'api_base': 'https://node-b.example',
        },
        status=403,
    )
    with pytest.raises(KlineShareAuthError) as ei:
        pro.realtime(symbol='600519.SS')
    assert ei.value.api_base == 'https://node-b.example'
    assert pro.base_url == 'https://data.klineshare.cn'
    assert pro.api_base == 'https://node-b.example'


def test_mid_session_node_reassignment_retries() -> None:
    """Already on old api_base; server reassigns → wrong-node 403 → switch."""
    pro, session = _client(limits='off')
    pro.base_url = 'https://old-node.example'
    pro._api_base = 'https://old-node.example'

    def _side_effect(url: str, **kwargs: Any) -> _FakeResp:
        if url.startswith('https://old-node.example/'):
            return _FakeResp(
                {
                    'success': False,
                    'code': 403,
                    'message': '当前入口不可用，请改用分配地址请求：https://new-node.example',
                    'api_base': 'https://new-node.example',
                },
                status=403,
            )
        assert url.startswith('https://new-node.example/')
        return _FakeResp({'success': True, 'data': {'symbol': '600519.SS'}})

    session.get.side_effect = _side_effect
    out = pro.realtime(symbol='600519.SS')
    assert out['symbol'] == '600519.SS'
    assert pro.base_url == 'https://new-node.example'
    urls = [c.args[0] for c in session.get.call_args_list]
    assert urls == [
        'https://old-node.example/v1/realtime',
        'https://new-node.example/v1/realtime',
    ]


def test_mid_session_reassignment_with_cached_limits() -> None:
    """limits=enforce with stale cache on old node still recovers via 403."""
    from klineshare.limits.snapshot import parse_me_payload

    pro, session = _client(limits='enforce')
    pro.base_url = 'https://old-node.example'
    pro._api_base = 'https://old-node.example'
    pro._limits = parse_me_payload({
        'success': True,
        'account': {},
        'scopes': [{
            'scope': 'realtime',
            'rate_limit': {'requests': 60, 'window_minutes': 1},
        }],
        'kline': {},
        'max_realtime_symbols': 10,
        'api_base': 'https://old-node.example',
    })

    def _side_effect(url: str, **kwargs: Any) -> _FakeResp:
        if url.startswith('https://old-node.example/') and not url.endswith('/v1/me'):
            return _FakeResp(
                {
                    'success': False,
                    'code': 403,
                    'message': '当前入口不可用，请改用分配地址请求：https://new-node.example',
                    'api_base': 'https://new-node.example',
                },
                status=403,
            )
        if url.endswith('/v1/me'):
            assert url.startswith('https://new-node.example/')
            return _FakeResp({
                'success': True,
                'account': {},
                'scopes': [{
                    'scope': 'realtime',
                    'rate_limit': {'requests': 60, 'window_minutes': 1},
                }],
                'kline': {},
                'max_realtime_symbols': 10,
                'api_base': 'https://new-node.example',
            })
        assert url == 'https://new-node.example/v1/realtime'
        return _FakeResp({'success': True, 'data': {'ok': 1}})

    session.get.side_effect = _side_effect
    assert pro.realtime(symbol='600519.SS') == {'ok': 1}
    assert pro.base_url == 'https://new-node.example'
    urls = [c.args[0] for c in session.get.call_args_list]
    assert urls[0] == 'https://old-node.example/v1/realtime'
    assert 'https://new-node.example/v1/me' in urls
    assert urls[-1] == 'https://new-node.example/v1/realtime'


def test_scope_denied_403_without_api_base_does_not_retry() -> None:
    pro, session = _client(limits='off')
    session.get.return_value = _FakeResp(
        {'success': False, 'code': 403, 'message': '未开通 realtime 权限'},
        status=403,
    )
    with pytest.raises(KlineShareAuthError):
        pro.realtime(symbol='600519.SS')
    assert session.get.call_count == 1
    assert pro.base_url == 'https://data.klineshare.cn'


def test_extract_api_base_from_ws_message() -> None:
    assert extract_api_base({
        'type': 'error',
        'code': 403,
        'message': '当前入口不可用，请改用分配地址请求：https://new.example api_base=https://new.example',
    }) == 'https://new.example'
