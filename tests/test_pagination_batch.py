"""Pagination + batch-fetch depth tests (unit + optional live).

Covers:
- iter_kline: cursor, max_pages, empty page, short page, stagnant cursor
- manual kline timestamp paging (ms→s)
- multi-symbol kline batch expand
- realtime / index / etf multi-symbol params
- realtime_v2 / auction_v2 all=True
- catalog offset/limit second page
- quota: kline batch ≤5, realtime max symbols
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from klineshare import Client, KlineShareQuotaError
from klineshare.client import set_api_key


class _FakeResp:
    def __init__(self, body: Any, status: int = 200) -> None:
        self._body = body
        self.status_code = status
        self.headers: Dict[str, str] = {}
        self.text = ''

    def json(self) -> Any:
        return self._body


def _client(session: MagicMock) -> Client:
    set_api_key('tg_test')
    return Client(
        api_key='tg_test',
        base_url='https://data.klineshare.cn',
        session=session,
        as_dataframe=False,
        limits='off',
    )


def _matrix_page(symbol: str, rows: List[list]) -> dict:
    return {
        'success': True,
        'fields': ['timestamp', 'close'],
        'symbols': {symbol: rows},
    }


# --------------------------------------------------------------------------- pagination
def test_iter_kline_stops_on_empty_page() -> None:
    session = MagicMock()
    session.headers = {}
    calls: List[Optional[int]] = []

    def _side(url, **kwargs):
        ts = kwargs.get('params', {}).get('timestamp')
        calls.append(ts)
        if ts is None:
            return _FakeResp(_matrix_page('600519.SS', [[2_000_000_000_000, 1.0], [1_900_000_000_000, 0.9]]))
        return _FakeResp({'success': True, 'fields': ['timestamp', 'close'], 'symbols': {}})

    session.get.side_effect = _side
    pro = _client(session)
    pages = list(pro.iter_kline(symbol='600519.SS', period=86400, count=2, max_pages=10))
    assert len(pages) == 1
    assert len(calls) == 2  # second fetch returned empty → stop


def test_iter_kline_stops_on_short_page() -> None:
    """When returned bars < count, do not request another page."""
    session = MagicMock()
    session.headers = {}
    calls: List[Optional[int]] = []

    def _side(url, **kwargs):
        calls.append(kwargs.get('params', {}).get('timestamp'))
        return _FakeResp(_matrix_page('600519.SS', [[1_700_000_000_000, 1.0]]))  # 1 < count=3

    session.get.side_effect = _side
    pro = _client(session)
    pages = list(pro.iter_kline(symbol='600519.SS', period=86400, count=3, max_pages=10))
    assert len(pages) == 1
    assert len(calls) == 1


def test_iter_kline_respects_max_pages() -> None:
    session = MagicMock()
    session.headers = {}
    n = {'i': 0}

    def _side(url, **kwargs):
        n['i'] += 1
        # always return full page so iterator would continue forever without max_pages
        base = 2_000_000_000_000 - n['i'] * 86_400_000
        return _FakeResp(
            _matrix_page(
                '600519.SS',
                [[base, 1.0], [base - 1, 0.9]],
            )
        )

    session.get.side_effect = _side
    pro = _client(session)
    pages = list(pro.iter_kline(symbol='600519.SS', period=86400, count=2, max_pages=3))
    assert len(pages) == 3
    assert n['i'] == 3


def test_iter_kline_stops_when_cursor_stagnates() -> None:
    session = MagicMock()
    session.headers = {}
    # same earliest timestamp every page → cursor would not advance after ms→s
    body = _matrix_page('600519.SS', [[1_700_000_000_500, 1.0], [1_700_000_000_400, 0.9]])

    def _side(url, **kwargs):
        return _FakeResp(body)

    session.get.side_effect = _side
    pro = _client(session)
    pages = list(pro.iter_kline(symbol='600519.SS', period=86400, count=2, max_pages=10))
    # first page yielded; second request same second-cursor → break
    assert len(pages) >= 1
    assert session.get.call_count <= 3


def test_manual_kline_pagination_timestamp_chain() -> None:
    session = MagicMock()
    session.headers = {}
    page1 = _matrix_page(
        '600519.SS',
        [[1_800_000_000_000, 2.0], [1_700_000_000_000, 1.0]],
    )
    page2 = _matrix_page('600519.SS', [[1_600_000_000_000, 0.5]])
    session.get.side_effect = [_FakeResp(page1), _FakeResp(page2)]
    pro = _client(session)

    bars = pro.kline(symbol='600519.SS', period=86400, count=2)
    earliest = min(b['timestamp'] for b in bars)
    older = pro.kline(symbol='600519.SS', period=86400, count=2, timestamp=earliest - 1)
    assert older[0]['close'] == 0.5
    # second call must send seconds
    ts = session.get.call_args_list[1].kwargs['params']['timestamp']
    assert ts == (earliest - 1) // 1000


# --------------------------------------------------------------------------- batch
def test_kline_multi_symbol_batch_expands_flat() -> None:
    session = MagicMock()
    session.headers = {}
    session.get.return_value = _FakeResp({
        'success': True,
        'fields': ['date', 'close'],
        'symbols': {
            '600519.SS': [['20250102', 100.0]],
            '000001.SZ': [['20250102', 10.0]],
            '000002.SZ': [['20250102', 11.0]],
        },
    })
    pro = _client(session)
    rows = pro.kline(symbol=['600519.SH', '000001.SZ', '000002.SZ'], period=86400, count=1)
    assert session.get.call_args.kwargs['params']['symbol'] == '600519.SS,000001.SZ,000002.SZ'
    assert len(rows) == 3
    assert {r['symbol'] for r in rows} == {'600519.SS', '000001.SZ', '000002.SZ'}


def test_kline_batch_over_5_rejected_when_enforce() -> None:
    set_api_key('tg_test')
    session = MagicMock()
    session.headers = {}
    me = {
        'account': {},
        'rate_limit': {'requests': 300, 'window_minutes': 1},
        'kline': {'max_count': 100, 'adjust_types': ['forward', 'none']},
        'max_realtime_symbols': 50,
        'scopes': {},
    }

    def _side(url, **kwargs):
        if url.endswith('/v1/me'):
            return _FakeResp({'success': True, 'data': me} if False else me)
        return _FakeResp({'success': True, 'data': []})

    # /v1/me returns unwrapped-style body via request unwrap — Client.refresh uses raw
    session.get.side_effect = lambda url, **kw: (
        _FakeResp(me) if str(url).endswith('/v1/me') else _FakeResp({'success': True, 'data': []})
    )
    pro = Client(
        api_key='tg_test',
        base_url='https://data.klineshare.cn',
        session=session,
        as_dataframe=False,
        limits='enforce',
        overflow='error',
    )
    syms = [f'{i:06d}.SS' for i in range(6)]
    with pytest.raises(KlineShareQuotaError) as ei:
        pro.kline(symbol=syms, period=86400, count=2)
    assert ei.value.limit_name == 'max_kline_batch_symbols'


def test_realtime_multi_symbol_and_v2_all() -> None:
    session = MagicMock()
    session.headers = {}
    session.get.return_value = _FakeResp({
        'success': True,
        'format': 'compact',
        'fields': ['symbol', 'price'],
        'sep': '|',
        'data': ['600519.SS|100', '000001.SZ|10'],
    })
    pro = _client(session)
    rows = pro.realtime(symbol=['600519.SH', '000001.SZ'])
    assert session.get.call_args.kwargs['params']['symbol'] == '600519.SS,000001.SZ'

    session.get.return_value = _FakeResp({
        'success': True,
        'format': 'compact',
        'fields': ['symbol', 'price'],
        'sep': '|',
        'data': ['600519.SS|100'],
    })
    pro.realtime_v2(all=True, market='SS')
    params = session.get.call_args.kwargs['params']
    assert params.get('all') == 1
    assert params.get('market') == 'SS'


def test_market_kline_v2_all_params() -> None:
    session = MagicMock()
    session.headers = {}
    session.get.return_value = _FakeResp({
        'success': True,
        'format': 'compact',
        'fields': ['symbol', 'bars_n', 'bars'],
        'sep': '|',
        'bars_fields': ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'amount'],
        'bars_sep': ',',
        'bars_row_sep': ';',
        'data': ['600519.SS|1|1760842440000,1338,1339,1337,1338.5,12000,16000000'],
    })
    pro = _client(session)
    rows = pro.market_kline_v2(all=True, market='SS', period=60, count=2)
    assert session.get.call_args.args[0].endswith('/v2/market-kline')
    params = session.get.call_args.kwargs['params']
    assert params.get('all') == 1
    assert params.get('market') == 'SS'
    assert params.get('period') == 60
    assert params.get('count') == 2
    assert rows[0]['symbol'] == '600519.SS'
    assert rows[0]['bars'][0]['close'] == 1338.5
    with pytest.raises(ValueError, match='all=True'):
        pro.market_kline_v2(all=False)


def test_index_etf_realtime_multi_symbol() -> None:
    session = MagicMock()
    session.headers = {}
    session.get.return_value = _FakeResp({'success': True, 'data': {'ok': 1}})
    pro = _client(session)
    pro.index_realtime(symbol=['000001.SH', '399001.SZ'])
    assert '000001.SS' in session.get.call_args.kwargs['params']['symbol']
    assert '399001.SZ' in session.get.call_args.kwargs['params']['symbol']
    pro.etf_realtime(symbol='510300.SS,510500.SS')
    assert session.get.call_args.kwargs['params']['symbol'] == '510300.SS,510500.SS'


def test_catalog_offset_limit_second_page_params() -> None:
    session = MagicMock()
    session.headers = {}
    session.get.return_value = _FakeResp({'success': True, 'data': []})
    pro = _client(session)
    pro.catalog_nodes(limit=10, offset=0)
    assert session.get.call_args.kwargs['params']['limit'] == 10
    assert session.get.call_args.kwargs['params']['offset'] == 0
    pro.catalog_nodes(limit=10, offset=10)
    assert session.get.call_args.kwargs['params']['offset'] == 10
    pro.catalog_node_members('industry', limit=5, offset=5)
    assert session.get.call_args.args[0].endswith('/v1/catalog/nodes/industry/members')
    assert session.get.call_args.kwargs['params']['offset'] == 5


def test_stocks_page_num_params() -> None:
    session = MagicMock()
    session.headers = {}
    session.get.return_value = _FakeResp({'success': True, 'data': []})
    pro = _client(session)
    pro.stocks(market='SS', page=2, num=20)
    params = session.get.call_args.kwargs['params']
    assert params['page'] == 2
    assert params['num'] == 20


# --------------------------------------------------------------------------- live (optional)
def _live_pro() -> Optional[Client]:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    for path in (os.path.join(root, '.env'),):
        if os.path.isfile(path):
            with open(path, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    k, _, v = line.partition('=')
                    k, v = k.strip(), v.strip().strip("'").strip('"')
                    if k and k not in os.environ:
                        os.environ[k] = v
    key = (os.getenv('KLINESHARE_API_KEY') or os.getenv('L2_API_KEY') or '').strip()
    if not key:
        return None
    base = (os.getenv('KLINESHARE_BASE_URL') or os.getenv('L2_API_BASE') or '').strip()
    kw: Dict[str, Any] = dict(api_key=key, as_dataframe=False, limits='enforce', on_rate_limit='wait')
    if base:
        kw['base_url'] = base
    return Client(**kw)


@pytest.mark.live
def test_live_iter_kline_two_pages_cursor_moves() -> None:
    if os.getenv('KLINESHARE_RUN_LIVE', '').strip() not in ('1', 'true', 'yes'):
        pytest.skip('set KLINESHARE_RUN_LIVE=1 to enable')
    pro = _live_pro()
    if pro is None:
        pytest.skip('no API key')
    pages = list(pro.iter_kline(symbol='600519.SS', period=86400, count=5, max_pages=2))
    assert len(pages) >= 1
    assert isinstance(pages[0], list) and pages[0]
    if len(pages) >= 2:
        t0 = min(b['timestamp'] for b in pages[0])
        t1 = min(b['timestamp'] for b in pages[1])
        assert t1 < t0, 'second page should be older'
    pro.close()


@pytest.mark.live
def test_live_kline_batch_three_symbols() -> None:
    if os.getenv('KLINESHARE_RUN_LIVE', '').strip() not in ('1', 'true', 'yes'):
        pytest.skip('set KLINESHARE_RUN_LIVE=1 to enable')
    pro = _live_pro()
    if pro is None:
        pytest.skip('no API key')
    rows = pro.kline(
        symbol=['600519.SS', '000001.SZ', '000002.SZ'],
        period=86400,
        count=2,
    )
    assert isinstance(rows, list)
    syms = {r.get('symbol') for r in rows}
    assert '600519.SS' in syms
    assert len(syms) >= 2
    pro.close()


@pytest.mark.live
def test_live_realtime_batch() -> None:
    if os.getenv('KLINESHARE_RUN_LIVE', '').strip() not in ('1', 'true', 'yes'):
        pytest.skip('set KLINESHARE_RUN_LIVE=1 to enable')
    pro = _live_pro()
    if pro is None:
        pytest.skip('no API key')
    data = pro.realtime(symbol=['600519.SS', '000001.SZ'], as_dataframe=False)
    # may be dict (single unwrap) or list depending on API
    assert data is not None
    pro.close()


@pytest.mark.live
def test_live_catalog_offset_pages() -> None:
    if os.getenv('KLINESHARE_RUN_LIVE', '').strip() not in ('1', 'true', 'yes'):
        pytest.skip('set KLINESHARE_RUN_LIVE=1 to enable')
    pro = _live_pro()
    if pro is None:
        pytest.skip('no API key')
    p0 = pro.catalog_nodes(limit=5, offset=0)
    p1 = pro.catalog_nodes(limit=5, offset=5)
    assert p0 is not None and p1 is not None
    if isinstance(p0, list) and isinstance(p1, list) and p0 and p1:
        # ideally disjoint; if API returns overlapping, at least both non-empty
        assert len(p0) <= 5 and len(p1) <= 5
    pro.close()
