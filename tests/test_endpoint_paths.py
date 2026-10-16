"""Assert each public endpoint method hits the expected HTTP path (mocked)."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import MagicMock

import pytest

from klineshare import Client
from klineshare.client import set_api_key


class _FakeResp:
    def __init__(self, body: Any = None, status: int = 200, text: str = '') -> None:
        self._body = body if body is not None else {'success': True, 'data': {}}
        self.status_code = status
        self.headers: Dict[str, str] = {}
        self.text = text or ''

    def json(self) -> Any:
        return self._body


def _client() -> Tuple[Client, MagicMock]:
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


# (method_name, kwargs, expected_path_suffix)
_CASES: List[Tuple[str, Dict[str, Any], str]] = [
    # meta
    ('health', {}, '/v1/health'),
    ('me', {}, '/v1/me'),
    ('public_catalog', {}, '/public/v1/catalog'),
    ('public_indices', {}, '/public/v1/indices'),
    ('public_metals', {}, '/public/v1/metals'),
    ('public_futures', {}, '/public/v1/futures'),
    ('public_futures_v2', {}, '/public/v1/futures-v2'),
    ('public_global_indices', {}, '/public/v1/global-indices'),
    ('public_global_bonds', {}, '/public/v1/global-bonds'),
    ('public_usstocks', {'keyword': 'AAPL', 'limit': 5}, '/public/v1/usstocks'),
    ('corp_schema', {}, '/public/v1/corp/schema'),
    ('finance_schema', {}, '/public/v1/finance/schema'),
    ('etf_schema', {}, '/public/v1/etf/schema'),
    ('bond_schema', {}, '/public/v1/bond/schema'),
    ('moneyflow_schema', {}, '/public/v1/moneyflow/schema'),
    ('moneyflow_ranking_catalog', {}, '/public/v1/moneyflow/ranking/catalog'),
    ('moneyflow_ranking_live_catalog', {}, '/public/v1/moneyflow/ranking/live/catalog'),
    ('moneyflow_live_catalog', {}, '/public/v1/moneyflow/live/catalog'),
    ('plate_moneyflow_schema', {}, '/public/v1/plate/moneyflow/schema'),
    ('moneyflow_ranking_live_stocks', {'offset': 0, 'limit': 50, 'sort': 'net'},
     '/v1/moneyflow/ranking/live/stocks'),
    ('moneyflow_live', {'symbol': '600519.SS'}, '/v1/moneyflow/live'),
    ('moneyflow_live', {'all': True}, '/v1/moneyflow/live'),
    # market
    ('realtime', {'symbol': '600519.SH'}, '/v1/realtime'),
    ('realtime_v2', {'symbol': '600519.SS'}, '/v2/realtime'),
    ('auction', {'symbol': '600519.SS'}, '/v1/auction'),
    ('auction_v2', {'symbol': '600519.SS'}, '/v2/auction'),
    ('trend', {'symbol': '600519.SS'}, '/v1/trend'),
    ('kline', {'symbol': '600519.SS', 'period': 86400, 'count': 2}, '/v2/kline'),
    ('adjust_factors', {'symbol': '600519.SS'}, '/v1/adjust-factors'),
    ('exrights', {'symbol': '600519.SS', 'count': 20}, '/v1/exrights'),
    ('adjust_params', {'symbol': '600519.SS', 'adjust_type': 'forward'}, '/v1/adjust-params'),
    ('bj_trend', {'symbol': '920000.BJ'}, '/v1/bj/trend'),
    ('bj_kline', {'symbol': '920000.BJ', 'period': 86400, 'count': 2}, '/v1/bj/kline'),
    ('stock', {'symbol': '600519.SS'}, '/v1/stock'),
    ('stocks', {}, '/v1/stocks'),
    ('corp', {'symbol': '600519.SS'}, '/v1/corp'),
    ('finance_report', {'symbol': '600519.SS'}, '/v1/finance/report'),
    ('calendar', {}, '/v1/calendar'),
    # index / etf
    ('index_realtime', {'symbol': '000001.SH'}, '/v1/index/realtime'),
    ('index_trend', {'symbol': '000001.SH'}, '/v1/index/trend'),
    ('index_kline', {'symbol': '000001.SH', 'period': 86400, 'count': 2}, '/v2/index/kline'),
    ('etf', {'symbol': '510300.SS'}, '/v1/etf'),
    ('etfs', {}, '/v1/etfs'),
    ('etf_realtime', {'symbol': '510300.SS'}, '/v1/etf/realtime'),
    ('etf_trend', {'symbol': '510300.SS'}, '/v1/etf/trend'),
    ('etf_kline', {'symbol': '510300.SS', 'period': 86400, 'count': 2}, '/v2/etf/kline'),
    # topics (sample)
    ('limit_up', {}, '/v1/limit-up'),
    ('limit_up_break', {}, '/v1/limit-up/break'),
    ('limit_down', {}, '/v1/limit-up/limit-down'),
    ('yesterday_limit_up', {}, '/v1/limit-up/yesterday'),
    ('limit_up_ladder', {}, '/v1/limit-up/ladder'),
    ('abnormal_events', {}, '/v1/abnormal-events'),
    ('lhb_dates', {}, '/v1/lhb/dates'),
    ('hot_money', {}, '/v1/hot-money'),
    ('moneyflow_daily_trend', {}, '/v1/moneyflow/daily-trend'),
    ('suspend_dates', {}, '/v1/suspend/dates'),
    ('zfpg_tabs', {}, '/v1/zfpg/tabs'),
    ('yjfp_tabs', {}, '/v1/yjfp/tabs'),
    # catalog / bond
    ('catalog_nodes', {}, '/v1/catalog/nodes'),
    ('catalog_node', {'node': 'a'}, '/v1/catalog/nodes/a'),
    ('catalog_plates', {}, '/v1/catalog/plates'),
    ('catalog_indices', {}, '/v1/catalog/indices'),
    ('catalog_stock', {'symbol': '600519.SS'}, '/v1/catalog/stocks/600519.SS'),
    ('bonds', {}, '/v1/bonds'),
    ('convertibles', {}, '/v1/convertibles'),
    ('convertible_realtime', {'symbol': '113052.SS'}, '/v1/convertible/realtime'),
    ('convertible_kline', {'symbol': '113052.SS', 'period': 86400, 'count': 2}, '/v2/convertible/kline'),
    ('bond_kline', {'symbol': '019547.SS', 'period': 86400, 'count': 2}, '/v1/bond/kline'),
    ('treasury_kline', {'symbol': '019547.SS', 'period': 86400, 'count': 2}, '/v1/treasury/kline'),
    ('enterprise_kline', {'symbol': '148000.SS', 'period': 86400, 'count': 2}, '/v1/enterprise/kline'),
    # extended
    ('metal_realtime', {}, '/v1/metal/realtime'),
    ('metal_kline', {'symbol': 'XAUUSD', 'period': 86400, 'count': 2}, '/v2/metal/kline'),
    ('futures_realtime', {}, '/v1/futures/realtime'),
    ('futures_kline', {'symbol': 'rb2501', 'period': 86400, 'count': 2}, '/v2/futures/kline'),
    ('futures_v2_realtime', {}, '/v1/futures-v2/realtime'),
    ('futures_v2_kline', {'symbol': 'rb2501', 'period': 86400, 'count': 2}, '/v2/futures-v2/kline'),
    ('global_index_realtime', {'symbol': 'DJI'}, '/v1/global-index/realtime'),
    ('global_index_kline', {'symbol': 'DJI', 'period': 86400, 'count': 2}, '/v2/global-index/kline'),
    ('global_bond_realtime', {'symbol': 'US10Y'}, '/v1/global-bond/realtime'),
    ('usstock_realtime', {'symbol': 'AAPL.US'}, '/v1/usstock/realtime'),
    ('usstock_kline', {'symbol': 'AAPL.US', 'period': 86400, 'count': 2}, '/v2/usstock/kline'),
    ('hkstock_realtime', {'symbol': '00700'}, '/v1/hkstock/realtime'),
    ('hkstock_trend', {'symbol': '00700.HK', 'day': 5}, '/v1/hkstock/trend'),
    ('hkstock_kline', {'symbol': 'HK00700', 'period': 86400, 'count': 2}, '/v2/hkstock/kline'),
    ('plate_realtime', {'plate_id': 'BK0001'}, '/v1/plate/realtime'),
    ('plate_kline', {'plate_id': 'BK0001', 'period': 86400, 'count': 2}, '/v2/plate/kline'),
    ('plate_moneyflow', {'plate_id': 'BK0001'}, '/v1/plate/moneyflow'),
    ('plate_moneyflow_ranking', {}, '/v1/plate/moneyflow/ranking'),
]


@pytest.mark.parametrize('method,kwargs,path', _CASES, ids=[f'{c[0]}{c[2]}' for c in _CASES])
def test_endpoint_path(method: str, kwargs: Dict[str, Any], path: str) -> None:
    pro, session = _client()
    fn: Callable[..., Any] = getattr(pro, method)
    fn(**kwargs)
    url = session.get.call_args.args[0]
    assert url.endswith(path), f'{method}: {url} does not end with {path}'


def test_hkstock_normalizes_bare_code() -> None:
    pro, session = _client()
    pro.hkstock_realtime(symbol='700')
    params = session.get.call_args.kwargs.get('params') or session.get.call_args.args[1]
    assert params.get('symbol') == '00700.HK'


def test_docs_md_uses_request_text() -> None:
    set_api_key('tg_test')
    session = MagicMock()
    session.headers = {}
    resp = MagicMock()
    resp.status_code = 200
    resp.text = '# hi'
    session.get.return_value = resp
    pro = Client(
        api_key='tg_test',
        base_url='https://data.klineshare.cn',
        session=session,
        as_dataframe=False,
        limits='off',
    )
    assert pro.docs_md() == '# hi'
    assert session.get.call_args.args[0].endswith('/public/v1/docs.md')


def test_ws_url_helpers() -> None:
    pro, _ = _client()
    assert '/v1/realtime/ws' in pro.realtime_ws_url(symbol='600519.SS')
    assert '/v1/futures/ws' in pro.futures_ws_url()
    assert '/v1/futures-v2/ws' in pro.futures_v2_ws_url()
