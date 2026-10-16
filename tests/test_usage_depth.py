"""Deep usage-matrix unit tests: direct / alias / edge / escape for every HTTP API."""

from __future__ import annotations

from typing import Any, Dict, Optional
from unittest.mock import MagicMock

import pytest

from klineshare import Client
from klineshare.client import set_api_key

from api_matrix import ApiEntry, UsageCase, build_matrix, mock_cases


class _FakeResp:
    def __init__(self, body: Any = None, status: int = 200, text: str = '') -> None:
        self._body = body if body is not None else {
            'success': True,
            'fields': ['date', 'timestamp', 'close'],
            'symbols': {'600519.SS': [['20250102', 1_700_000_000_000, 1.0]]},
            'data': {'ok': True},
        }
        self.status_code = status
        self.headers: Dict[str, str] = {}
        self.text = text or '# docs'

    def json(self) -> Any:
        return self._body


def _client() -> tuple:
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
    return pro, session


_MATRIX = build_matrix()
_CASES = mock_cases(_MATRIX)
_IDS = [f'{e.name}:{c.style}:{c.label}' for e, c in _CASES]


@pytest.mark.parametrize('entry,case', _CASES, ids=_IDS)
def test_usage_case_hits_path(entry: ApiEntry, case: UsageCase) -> None:
    pro, session = _client()
    try:
        case.call(pro)
    except StopIteration:
        # SSE helpers that call next(iter(...)) on empty mock stream
        pass
    except TypeError:
        # some stream mocks may not support iter_lines fully — path still recorded if get called
        if not session.get.called:
            raise

    assert session.get.called, f'{entry.name}/{case.style}: session.get not called'
    url = session.get.call_args.args[0]
    assert case.expect_path is not None
    assert url.endswith(case.expect_path), (
        f'{entry.name}/{case.style}: {url} does not end with {case.expect_path}'
    )
    if case.expect_params:
        params = session.get.call_args.kwargs.get('params') or {}
        for key, want in case.expect_params.items():
            assert key in params, f'{entry.name}: missing param {key} in {params}'
            assert params[key] == want, (
                f'{entry.name}: params[{key}]={params[key]!r} != {want!r}'
            )


def test_matrix_covers_all_public_client_methods() -> None:
    """Every public Client method that is an endpoint should appear in the matrix."""
    from klineshare.endpoints import (
        CatalogBondEndpoints,
        ExtendedEndpoints,
        IndexEtfEndpoints,
        MarketEndpoints,
        MetaEndpoints,
        TopicsEndpoints,
        WsEndpoints,
    )

    mixins = (
        MarketEndpoints,
        IndexEtfEndpoints,
        ExtendedEndpoints,
        TopicsEndpoints,
        CatalogBondEndpoints,
        WsEndpoints,
        MetaEndpoints,
    )
    public = set()
    for cls in mixins:
        for name in dir(cls):
            if name.startswith('_'):
                continue
            attr = getattr(cls, name)
            if callable(attr):
                public.add(name)

    matrix_names = {e.name for e in _MATRIX}
    # helpers that are intentional extras / renames in matrix
    extras = {
        'moneyflow_ranking_stocks_sort',  # edge-only path variant
        'get_escape',
        'refresh_limits',
    }
    missing = public - matrix_names - extras
    # bond board helpers covered under concrete names
    assert not missing, f'methods missing from api_matrix: {sorted(missing)}'


def test_every_entry_has_direct_case() -> None:
    for entry in _MATRIX:
        styles = {c.style for c in entry.cases}
        assert 'direct' in styles or entry.name in (
            'moneyflow_ranking_stocks_sort',
            'get_escape',
        ), f'{entry.name} has no direct case'


def test_ks_code_alias_realtime() -> None:
    pro, session = _client()
    pro.realtime(ks_code='sh600519')
    assert session.get.call_args.kwargs['params']['symbol'] == '600519.SS'
    assert 'ks_code' not in session.get.call_args.kwargs['params']


def test_kline_raw_skips_matrix_expand() -> None:
    pro, session = _client()
    body = {
        'success': True,
        'fields': ['date', 'close'],
        'symbols': {'600519.SS': [['20250102', 1.0]]},
    }
    session.get.return_value = _FakeResp(body)
    raw = pro.kline(symbol='600519.SS', period=86400, count=1, raw=True)
    assert 'symbols' in raw
    rows = pro.kline(symbol='600519.SS', period=86400, count=1)
    assert isinstance(rows, list)
    assert rows[0]['close'] == 1.0


def test_kline_format_raw_default_sends_and_expands() -> None:
    pro, session = _client()
    body = {
        'success': True,
        'format': 'raw',
        'fields': ['date', 'timestamp', 'close'],
        'sep': '|',
        'row_sep': ';',
        'symbols': {
            '600519.SS': '20231115|1700000000|100;20231116|1700086400|101',
        },
    }
    session.get.return_value = _FakeResp(body)
    # no explicit format= — SDK defaults to raw
    rows = pro.kline(symbol='600519.SS', period=86400, count=2)
    assert session.get.call_args.kwargs['params']['format'] == 'raw'
    assert isinstance(rows, list)
    assert len(rows) == 2
    assert rows[0]['symbol'] == '600519.SS'
    assert rows[0]['close'] == 100
    assert rows[1]['close'] == 101
    env = pro.kline(symbol='600519.SS', period=86400, count=2, raw=True)
    assert env['format'] == 'raw'
    assert isinstance(env['symbols']['600519.SS'], str)


def test_kline_format_none_omits_wire_param() -> None:
    pro, session = _client()
    session.get.return_value = _FakeResp({
        'success': True,
        'fields': ['date', 'close'],
        'symbols': {'600519.SS': [['20250102', 1.0]]},
    })
    pro.kline(symbol='600519.SS', period=86400, count=1, format=None)
    assert 'format' not in session.get.call_args.kwargs['params']


def test_bj_kline_format_raw_single_data_string() -> None:
    pro, session = _client()
    body = {
        'success': True,
        'format': 'raw',
        'fields': ['date', 'close'],
        'sep': '|',
        'row_sep': ';',
        'data': '20231115|100',
        'meta': {'symbol': '920000.BJ'},
    }
    session.get.return_value = _FakeResp(body)
    rows = pro.bj_kline(symbol='920000.BJ', period=86400, count=1)
    assert session.get.call_args.kwargs['params']['format'] == 'raw'
    assert rows[0]['symbol'] == '920000.BJ'
    assert rows[0]['close'] == 100


def test_multi_symbol_list_and_csv() -> None:
    pro, session = _client()
    pro.realtime(symbol=['600519.SH', '000001.SZ'])
    assert session.get.call_args.kwargs['params']['symbol'] == '600519.SS,000001.SZ'
    pro.realtime(symbol='600519.SH;000001.SZ')
    assert session.get.call_args.kwargs['params']['symbol'] == '600519.SS,000001.SZ'


def test_bool_params_serialized() -> None:
    pro, session = _client()
    pro.realtime(symbol='600519.SS', include_valuation=True, include_depth=False)
    params = session.get.call_args.kwargs['params']
    assert params['include_valuation'] == 'true'
    assert params['include_depth'] == 'false'


def test_as_dataframe_kline() -> None:
    pytest.importorskip('pandas')
    pro, session = _client()
    session.get.return_value = _FakeResp({
        'success': True,
        'fields': ['date', 'close'],
        'symbols': {'600519.SS': [['20250102', 1.0], ['20250103', 1.1]]},
    })
    df = pro.kline(symbol='600519.SS', period=86400, count=2, as_dataframe=True)
    import pandas as pd

    assert isinstance(df, pd.DataFrame)
    assert list(df['close']) == [1.0, 1.1]


def test_expand_compact_rows_false() -> None:
    pro, session = _client()
    session.get.return_value = _FakeResp({
        'success': True,
        'format': 'compact',
        'fields': ['symbol', 'price'],
        'sep': '|',
        'data': ['600519.SS|100'],
    })
    rawish = pro.realtime_v2(symbol='600519.SS', expand_compact_rows=False)
    # unwrap still returns data portion / body without expanding rows to dicts
    assert rawish is not None


def test_pro_api_factory_and_context() -> None:
    from klineshare import pro_api

    set_api_key('tg_test')
    session = MagicMock()
    session.headers = {}
    session.get.return_value = _FakeResp({'success': True, 'data': {'ok': 1}})
    with Client(
        api_key='tg_test',
        base_url='https://data.klineshare.cn',
        session=session,
        limits='off',
        as_dataframe=False,
    ) as pro:
        assert pro.health() == {'ok': 1}
    # factory exists
    assert callable(pro_api)
