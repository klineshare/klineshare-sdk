"""Canonical API usage matrix for tests, live smoke, and docs generation.

Each entry describes how to call a Client method in several styles:
- direct: 用法（基本调用）
- alias: 用法（参数别名，如 ks_code / symbols / tradedate / q）
- edge: 进阶用法（附加字段、批量、翻页、raw 等）
- escape: Client.get(path) / request（测试覆盖用，文档不展开）

``call`` is a callable ``(pro) -> result`` used by live smoke.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence


@dataclass(frozen=True)
class UsageCase:
    """One concrete invocation of an API."""

    style: str  # direct | alias | escape | edge | factory
    label: str
    call: Callable[[Any], Any]
    expect_path: Optional[str] = None
    expect_params: Optional[Dict[str, Any]] = None  # subset match
    live: bool = True  # include in live smoke
    optional_live: bool = False  # 403/503 ok in live


@dataclass(frozen=True)
class ApiEntry:
    name: str
    group: str
    path: str
    kind: str  # http | sse | ws | local | text | helper
    summary: str
    cases: Sequence[UsageCase] = field(default_factory=tuple)


def _paths(pro: Any) -> None:
    """Marker — unused."""


# --------------------------------------------------------------------------- builders
def _http(
    name: str,
    group: str,
    path: str,
    summary: str,
    *,
    direct: Callable[[Any], Any],
    alias: Optional[Callable[[Any], Any]] = None,
    edge: Optional[Callable[[Any], Any]] = None,
    expect_params_direct: Optional[Dict[str, Any]] = None,
    expect_params_alias: Optional[Dict[str, Any]] = None,
    expect_params_edge: Optional[Dict[str, Any]] = None,
    optional_live: bool = False,
    live: bool = True,
    direct_label: Optional[str] = None,
    alias_label: Optional[str] = None,
    edge_label: Optional[str] = None,
) -> ApiEntry:
    cases: List[UsageCase] = [
        UsageCase(
            'direct',
            direct_label or '基本调用',
            direct,
            expect_path=path,
            expect_params=expect_params_direct,
            live=live,
            optional_live=optional_live,
        )
    ]
    if alias is not None:
        cases.append(
            UsageCase(
                'alias',
                alias_label or '参数别名',
                alias,
                expect_path=path,
                expect_params=expect_params_alias or expect_params_direct,
                live=False,
            )
        )
    if edge is not None:
        cases.append(
            UsageCase(
                'edge',
                edge_label or '进阶参数',
                edge,
                expect_path=path,
                expect_params=expect_params_edge,
                live=False,
            )
        )
    # escape hatch via get()
    cases.append(
        UsageCase(
            'escape',
            f'{name} via get({path})',
            lambda pro, p=path: pro.get(p, auth=not p.startswith('/public')),
            expect_path=path,
            live=False,
        )
    )
    return ApiEntry(name, group, path, 'http', summary, tuple(cases))


def build_matrix() -> List[ApiEntry]:
    """Full public surface matrix."""
    S = '600519.SS'
    SH = '600519.SH'
    SZ = '000001.SZ'
    IDX = '000001.SH'
    ETF = '510300.SS'
    BJ = '920000.BJ'
    entries: List[ApiEntry] = []

    # ---- meta ----
    entries += [
        _http(
            'health', 'meta', '/v1/health', '服务健康检查',
            direct=lambda p: p.health(),
            edge=lambda p: p.health(raw=True),
        ),
        _http(
            'me', 'meta', '/v1/me', '当前密钥权限与限额',
            direct=lambda p: p.me(),
            edge=lambda p: p.me(raw=True),
        ),
        _http(
            'public_catalog', 'meta', '/public/v1/catalog', '公开目录/档位',
            direct=lambda p: p.public_catalog(),
        ),
        _http(
            'public_indices', 'meta', '/public/v1/indices', '公开指数列表',
            direct=lambda p: p.public_indices(limit=5),
            edge=lambda p: p.public_indices(keyword='沪深', listed=True),
            expect_params_direct={'limit': 5},
        ),
        _http(
            'public_metals', 'meta', '/public/v1/metals', '贵金属公开清单',
            direct=lambda p: p.public_metals(limit=5),
            expect_params_direct={'limit': 5},
        ),
        _http(
            'public_futures', 'meta', '/public/v1/futures', '期货 v1 公开清单',
            direct=lambda p: p.public_futures(keyword='黄金', limit=5),
            expect_params_direct={'keyword': '黄金', 'limit': 5},
        ),
        _http(
            'public_futures_v2', 'meta', '/public/v1/futures-v2', '期货 v2 公开清单',
            direct=lambda p: p.public_futures_v2(exchange='SHFE'),
            expect_params_direct={'exchange': 'SHFE'},
        ),
        _http(
            'public_global_indices', 'meta', '/public/v1/global-indices', '全球指数公开清单',
            direct=lambda p: p.public_global_indices(keyword='道指', limit=5),
        ),
        _http(
            'public_global_bonds', 'meta', '/public/v1/global-bonds', '国际债券公开清单',
            direct=lambda p: p.public_global_bonds(keyword='美债', limit=5),
        ),
        _http(
            'public_usstocks', 'meta', '/public/v1/usstocks', '美股公开清单/搜索',
            direct=lambda p: p.public_usstocks(keyword='AAPL', limit=5),
            expect_params_direct={'keyword': 'AAPL', 'limit': 5},
        ),
        _http('corp_schema', 'meta', '/public/v1/corp/schema', '公司资料字段结构',
              direct=lambda p: p.corp_schema()),
        _http('finance_schema', 'meta', '/public/v1/finance/schema', '财务字段结构',
              direct=lambda p: p.finance_schema()),
        _http('etf_schema', 'meta', '/public/v1/etf/schema', '基金字段结构',
              direct=lambda p: p.etf_schema()),
        _http('bond_schema', 'meta', '/public/v1/bond/schema', '债券字段结构',
              direct=lambda p: p.bond_schema()),
        _http('moneyflow_schema', 'meta', '/public/v1/moneyflow/schema', '资金流字段结构',
              direct=lambda p: p.moneyflow_schema()),
        _http('moneyflow_ranking_catalog', 'meta', '/public/v1/moneyflow/ranking/catalog',
              '新浪资金流榜单目录', direct=lambda p: p.moneyflow_ranking_catalog()),
        _http('moneyflow_ranking_live_catalog', 'meta', '/public/v1/moneyflow/ranking/live/catalog',
              '实时资金流榜单目录', direct=lambda p: p.moneyflow_ranking_live_catalog()),
        _http('moneyflow_live_catalog', 'meta', '/public/v1/moneyflow/live/catalog',
              '实时个股资金流（按码）目录', direct=lambda p: p.moneyflow_live_catalog()),
        _http('plate_moneyflow_schema', 'meta', '/public/v1/plate/moneyflow/schema',
              '板块资金流字段说明', direct=lambda p: p.plate_moneyflow_schema()),
    ]
    entries.append(
        ApiEntry(
            'docs_md', 'meta', '/public/v1/docs.md', 'text',
            '接口说明文档',
            (
                UsageCase('direct', 'docs_md()', lambda p: p.docs_md(), '/public/v1/docs.md'),
                UsageCase(
                    'escape', 'request_text',
                    lambda p: p.request_text('/public/v1/docs.md'),
                    '/public/v1/docs.md', live=False,
                ),
            ),
        )
    )
    entries.append(
        ApiEntry(
            'llms_txt', 'meta', '/public/v1/llms.txt', 'text',
            '大模型短文档',
            (UsageCase('direct', 'llms_txt()', lambda p: p.llms_txt(), '/public/v1/llms.txt'),),
        )
    )
    entries.append(
        ApiEntry(
            'llms_full_txt', 'meta', '/public/v1/llms-full.txt', 'text',
            '大模型全文档',
            (UsageCase('direct', 'llms_full_txt()', lambda p: p.llms_full_txt(), '/public/v1/llms-full.txt'),),
        )
    )

    # ---- market ----
    entries += [
        _http(
            'realtime', 'market', '/v1/realtime', '个股实时',
            direct=lambda p: p.realtime(symbol=SH),
            alias=lambda p: p.realtime(ks_code='sh600519'),
            edge=lambda p: p.realtime(symbol=[SH, SZ], include_valuation=True, include_depth=True),
            expect_params_direct={'symbol': S},
            expect_params_alias={'symbol': S},
            expect_params_edge={'symbol': f'{S},{SZ}', 'include_valuation': 'true', 'include_depth': 'true'},
        ),
        ApiEntry(
            'realtime_v2', 'market', '/v2/realtime', 'http',
            '全市场紧凑格式实时（一般用 all=True）',
            (
                UsageCase(
                    'direct', '全市场（推荐）',
                    lambda p: p.realtime_v2(all=True, market='SS'),
                    '/v2/realtime',
                    expect_params={'all': 1, 'market': 'SS'},
                    # 全量响应大，冒烟用单标的即可
                    live=False,
                ),
                UsageCase(
                    'edge', '指定标的 / 批量',
                    lambda p: p.realtime_v2(symbol=S),
                    '/v2/realtime',
                    expect_params={'symbol': S},
                    optional_live=True,
                ),
                UsageCase(
                    'edge', '全市场含估值与盘口',
                    lambda p: p.realtime_v2(
                        all=True, market='SS', include_valuation=True, include_depth=True,
                    ),
                    '/v2/realtime',
                    expect_params={
                        'all': 1, 'market': 'SS',
                        'include_valuation': 'true', 'include_depth': 'true',
                    },
                    live=False,
                ),
                UsageCase(
                    'escape', 'realtime_v2 via get(/v2/realtime)',
                    lambda p: p.get('/v2/realtime'),
                    '/v2/realtime', live=False,
                ),
            ),
        ),
        _http(
            'auction', 'market', '/v1/auction', '集合竞价分时（单标的）',
            direct=lambda p: p.auction(symbol=S),
            alias=lambda p: p.auction(ks_code=SH),
            expect_params_direct={'symbol': S},
            optional_live=True,
        ),
        ApiEntry(
            'auction_v2', 'market', '/v2/auction', 'http',
            '集合竞价紧凑格式（一般用 all=True 拉全市场）',
            (
                UsageCase(
                    'direct', '全市场（推荐）',
                    lambda p: p.auction_v2(all=True, market='SS'),
                    '/v2/auction',
                    expect_params={'all': 1, 'market': 'SS'},
                    live=False,
                ),
                UsageCase(
                    'edge', '全市场含分时明细',
                    lambda p: p.auction_v2(all=True, include_minutes=True),
                    '/v2/auction',
                    expect_params={'all': 1, 'include_minutes': 'true'},
                    live=False,
                ),
                UsageCase(
                    'edge', '指定标的',
                    lambda p: p.auction_v2(symbol=S),
                    '/v2/auction',
                    expect_params={'symbol': S},
                    optional_live=True,
                ),
                UsageCase(
                    'escape', 'auction_v2 via get(/v2/auction)',
                    lambda p: p.get('/v2/auction'),
                    '/v2/auction', live=False,
                ),
            ),
        ),
        ApiEntry(
            'market_kline_v2', 'market', '/v2/market-kline', 'http',
            '全市场近端分钟 K compact（仅 all=True；独立 scope）',
            (
                UsageCase(
                    'direct', '全市场（推荐）',
                    lambda p: p.market_kline_v2(all=True, market='SS', period=60, count=2),
                    '/v2/market-kline',
                    expect_params={'all': 1, 'market': 'SS', 'period': 60, 'count': 2},
                    live=False,
                ),
                UsageCase(
                    'edge', '沪深京（CN）',
                    lambda p: p.market_kline_v2(all=True, market='CN', count=2),
                    '/v2/market-kline',
                    expect_params={'all': 1, 'market': 'CN', 'count': 2},
                    live=False,
                ),
                UsageCase(
                    'escape', 'market_kline_v2 via get(/v2/market-kline)',
                    lambda p: p.get('/v2/market-kline', params={'all': 1}),
                    '/v2/market-kline', live=False,
                ),
            ),
        ),
        _http(
            'trend', 'market', '/v1/trend', '分时',
            direct=lambda p: p.trend(symbol=S),
            alias=lambda p: p.trend(ks_code=SH, date='20250102'),
            expect_params_alias={'symbol': S, 'date': '20250102'},
        ),
        ApiEntry(
            'kline', 'market', '/v2/kline', 'http',
            'K线（默认 raw 格式并展开为行）',
            (
                UsageCase(
                    'direct', '日线前复权',
                    lambda p: p.kline(symbol=SH, period=86400, adjust_type='forward', count=5),
                    '/v2/kline',
                    expect_params={
                        'symbol': S, 'period': 86400, 'adjust_type': 'forward',
                        'count': 5, 'format': 'raw',
                    },
                ),
                UsageCase(
                    'alias', 'ks_code 别名',
                    lambda p: p.kline(ks_code='600519', period=86400, count=3),
                    '/v2/kline',
                    expect_params={'symbol': S, 'period': 86400, 'count': 3, 'format': 'raw'},
                    live=False,
                ),
                UsageCase(
                    'edge', '毫秒 timestamp 翻页 + raw 信封',
                    lambda p: p.kline(
                        symbol=S, period=86400, count=2, timestamp=1_784_073_600_000, raw=True,
                    ),
                    '/v2/kline',
                    expect_params={'symbol': S, 'timestamp': 1_784_073_600, 'format': 'raw'},
                    live=False,
                ),
                UsageCase(
                    'edge', 'format=None 使用服务端列式',
                    lambda p: p.kline(symbol=S, period=86400, count=2, format=None),
                    '/v2/kline',
                    expect_params={'symbol': S, 'period': 86400, 'count': 2},
                    live=False,
                ),
                UsageCase(
                    'escape', 'kline via get(/v2/kline)',
                    lambda p: p.get('/v2/kline'),
                    '/v2/kline',
                    live=False,
                ),
            ),
        ),
        ApiEntry(
            'iter_kline', 'market', '/v2/kline', 'helper',
            'K线向更早翻页迭代',
            (
                UsageCase(
                    'direct', 'iter_kline max_pages=2',
                    lambda p: list(p.iter_kline(symbol=S, period=86400, count=3, max_pages=2)),
                    '/v2/kline',
                ),
                UsageCase(
                    'alias', 'iter_kline ks_code',
                    lambda p: list(p.iter_kline(ks_code=SH, period=86400, count=2, max_pages=1)),
                    '/v2/kline', live=False,
                ),
                UsageCase(
                    'edge', 'manual timestamp page chain',
                    lambda p: (
                        lambda bars: p.kline(
                            symbol=S,
                            period=86400,
                            count=3,
                            timestamp=min(b['timestamp'] for b in bars) - 1,
                        )
                    )(p.kline(symbol=S, period=86400, count=3)),
                    '/v2/kline',
                    live=True,
                ),
            ),
        ),
        ApiEntry(
            'kline_batch', 'market', '/v2/kline', 'http',
            'K线多标的批量（最多5个）',
            (
                UsageCase(
                    'direct', 'kline 3 symbols',
                    lambda p: p.kline(
                        symbol=['600519.SS', '000001.SZ', '000002.SZ'],
                        period=86400,
                        count=2,
                    ),
                    '/v2/kline',
                    expect_params={'symbol': '600519.SS,000001.SZ,000002.SZ'},
                ),
            ),
        ),
        ApiEntry(
            'realtime_batch', 'market', '/v1/realtime', 'http',
            '实时多标的批量',
            (
                UsageCase(
                    'direct', 'realtime 2 symbols',
                    lambda p: p.realtime(symbol=[SH, SZ]),
                    '/v1/realtime',
                    expect_params={'symbol': f'{S},{SZ}'},
                ),
            ),
        ),
        ApiEntry(
            'catalog_nodes_page', 'catalog', '/v1/catalog/nodes', 'http',
            '目录翻页（offset/limit）',
            (
                UsageCase(
                    'direct', 'offset=0 then 5',
                    lambda p: (p.catalog_nodes(limit=5, offset=0), p.catalog_nodes(limit=5, offset=5)),
                    '/v1/catalog/nodes',
                    optional_live=True,
                ),
            ),
        ),
        _http(
            'adjust_factors', 'market', '/v1/adjust-factors', '复权因子',
            direct=lambda p: p.adjust_factors(symbol=S),
            edge=lambda p: p.adjust_factors(symbol=S, start='20200101', end='20250101'),
        ),
        _http(
            'exrights', 'market', '/v1/exrights', '除权除息',
            direct=lambda p: p.exrights(symbol=S, count=20),
            edge=lambda p: p.exrights(symbol=S, start='20200101', end='20241231'),
        ),
        _http(
            'adjust_params', 'market', '/v1/adjust-params', '复权参数',
            direct=lambda p: p.adjust_params(symbol=S, adjust_type='forward', count=64),
            edge=lambda p: p.adjust_params(symbol=S, adjust_type='backward', start='20200101'),
        ),
        _http(
            'bj_trend', 'market', '/v1/bj/trend', '北交所分时',
            direct=lambda p: p.bj_trend(symbol=BJ, date='20260824'),
            optional_live=True,
        ),
        _http(
            'bj_kline', 'market', '/v1/bj/kline', '北交所K线',
            direct=lambda p: p.bj_kline(symbol=BJ, period=86400, count=3),
            optional_live=True,
        ),
        _http(
            'stock', 'market', '/v1/stock', '个股基础信息',
            direct=lambda p: p.stock(symbol=S),
            alias=lambda p: p.stock(ks_code=SH),
        ),
        _http(
            'stocks', 'market', '/v1/stocks', '股票列表搜索',
            direct=lambda p: p.stocks(keyword='茅台', limit=5),
            edge=lambda p: p.stocks(market='SS', page=1, num=10),
        ),
        _http(
            'corp', 'market', '/v1/corp', '公司资料',
            direct=lambda p: p.corp(symbol=S),
        ),
        _http(
            'finance_report', 'market', '/v1/finance/report', '财务报表',
            direct=lambda p: p.finance_report(symbol=S),
            edge=lambda p: p.finance_report(symbol=S, year=2024, period='Q4'),
            optional_live=True,
        ),
        _http(
            'calendar', 'market', '/v1/calendar', '交易日历',
            direct=lambda p: p.calendar(),
            edge=lambda p: p.calendar(start='20250101', end='20250131'),
        ),
    ]

    # ---- index / etf ----
    entries += [
        _http(
            'index_realtime', 'index_etf', '/v1/index/realtime', '指数实时',
            direct=lambda p: p.index_realtime(symbol=IDX),
            alias=lambda p: p.index_realtime(ks_code='000001.SH'),
        ),
        _http(
            'index_trend', 'index_etf', '/v1/index/trend', '指数分时',
            direct=lambda p: p.index_trend(symbol=IDX),
        ),
        _http(
            'index_kline', 'index_etf', '/v2/index/kline', '指数K线',
            direct=lambda p: p.index_kline(symbol=IDX, period=86400, count=3),
            expect_params_direct={'symbol': '000001.SS', 'period': 86400, 'count': 3, 'adjust_type': 'none'},
        ),
        _http(
            'etf', 'index_etf', '/v1/etf', '基金资料',
            direct=lambda p: p.etf(symbol=ETF),
        ),
        _http(
            'etfs', 'index_etf', '/v1/etfs', '基金列表',
            direct=lambda p: p.etfs(keyword='沪深300', limit=5),
        ),
        _http(
            'etf_realtime', 'index_etf', '/v1/etf/realtime', '基金实时',
            direct=lambda p: p.etf_realtime(symbol=ETF),
        ),
        _http(
            'etf_trend', 'index_etf', '/v1/etf/trend', '基金分时',
            direct=lambda p: p.etf_trend(symbol=ETF),
        ),
        _http(
            'etf_kline', 'index_etf', '/v2/etf/kline', '基金K线',
            direct=lambda p: p.etf_kline(symbol=ETF, period=86400, count=3),
        ),
    ]

    # ---- topics ----
    for name, path, summary in [
        ('limit_up', '/v1/limit-up', '涨停池'),
        ('limit_up_break', '/v1/limit-up/break', '破板'),
        ('limit_down', '/v1/limit-up/limit-down', '跌停'),
        ('yesterday_limit_up', '/v1/limit-up/yesterday', '昨日涨停'),
        ('limit_up_ladder', '/v1/limit-up/ladder', '连板天梯'),
    ]:
        entries.append(
            _http(name, 'topics', path, summary, direct=lambda p, n=name: getattr(p, n)())
        )
    for name, path, summary in [
        ('limit_up_plates_trending', '/v1/limit-up/plates/trending', '涨停板块热度'),
        ('limit_up_plates_industry', '/v1/limit-up/plates/industry', '涨停行业板块'),
        ('limit_up_plates_concept', '/v1/limit-up/plates/concept', '涨停概念板块'),
        ('limit_up_plates_style', '/v1/limit-up/plates/style', '涨停风格板块'),
    ]:
        entries.append(
            _http(
                name, 'topics', path, summary,
                direct=lambda p, n=name: getattr(p, n)(limit=5),
                expect_params_direct={'limit': 5},
            )
        )
    entries += [
        _http(
            'abnormal_events', 'topics', '/v1/abnormal-events', '异动事件',
            direct=lambda p: p.abnormal_events(count=10),
            edge=lambda p: p.abnormal_events(types='limit_up', kind='stock'),
        ),
        ApiEntry(
            'abnormal_events_stream', 'topics', '/v1/abnormal-events/stream', 'sse',
            '异动推流',
            (
                UsageCase(
                    'direct', 'abnormal_events_stream one event',
                    lambda p: next(iter(p.abnormal_events_stream())),
                    '/v1/abnormal-events/stream',
                    optional_live=True,
                ),
            ),
        ),
        ApiEntry(
            'market_flash_stream', 'topics', '/v1/market-flash/stream', 'sse',
            '快讯推流',
            (
                UsageCase(
                    'direct', 'market_flash_stream',
                    lambda p: next(iter(p.market_flash_stream())),
                    '/v1/market-flash/stream',
                    optional_live=True,
                ),
            ),
        ),
        _http(
            'lhb_daily', 'topics', '/v1/lhb/daily', '龙虎榜日数据',
            direct=lambda p: p.lhb_daily(),
            alias=lambda p: p.lhb_daily(tradedate='20250102'),
            optional_live=True,
        ),
        _http(
            'lhb_stock', 'topics', '/v1/lhb/stock', '龙虎榜个股',
            direct=lambda p: p.lhb_stock(symbol=S, bdate='2026-07-01', edate='2026-07-10'),
            optional_live=True,
        ),
        _http(
            'lhb', 'topics', '/v1/lhb', '龙虎榜综合',
            direct=lambda p: p.lhb(symbol=S, bdate='2026-07-01', edate='2026-07-10'),
            optional_live=True,
        ),
        _http('lhb_dates', 'topics', '/v1/lhb/dates', '龙虎榜日期',
              direct=lambda p: p.lhb_dates()),
        _http(
            'lhb_stats', 'topics', '/v1/lhb/stats', '龙虎榜统计',
            direct=lambda p: p.lhb_stats(),
            optional_live=True,
        ),
        _http(
            'hot_money', 'topics', '/v1/hot-money', '游资名录',
            direct=lambda p: p.hot_money(),
            alias=lambda p: p.hot_money(q='章盟主'),
            optional_live=True,
        ),
        _http(
            'hot_money_seat', 'topics', '/v1/hot-money/seat', '游资席位',
            direct=lambda p: p.hot_money_seat(
                broker='兴业证券股份有限公司南京天元东路证券营业部',
            ),
            optional_live=True,
        ),
        _http(
            'hot_money_detail', 'topics', '/v1/hot-money/detail', '游资明细',
            direct=lambda p: p.hot_money_detail(name='92科比'),
            optional_live=True,
        ),
        _http('hot_money_stats', 'topics', '/v1/hot-money/stats', '游资统计',
              direct=lambda p: p.hot_money_stats(), optional_live=True),
        _http(
            'moneyflow_daily_trend', 'topics', '/v1/moneyflow/daily-trend', '资金流日趋势',
            direct=lambda p: p.moneyflow_daily_trend(symbol=S),
            optional_live=True,
        ),
        _http(
            'moneyflow_stage', 'topics', '/v1/moneyflow/stage', '资金流阶段',
            direct=lambda p: p.moneyflow_stage(symbol=S),
            optional_live=True,
        ),
        _http(
            'moneyflow_distribution', 'topics', '/v1/moneyflow/distribution', '资金流分布',
            direct=lambda p: p.moneyflow_distribution(symbol=S),
            optional_live=True,
        ),
        _http(
            'moneyflow_ranking_boards', 'topics', '/v1/moneyflow/ranking/boards', '板块资金榜',
            direct=lambda p: p.moneyflow_ranking_boards(category='industry'),
            expect_params_direct={'category': 'industry'},
            optional_live=True,
        ),
        _http(
            'moneyflow_ranking_stocks', 'topics', '/v1/moneyflow/ranking/stocks', '个股资金榜',
            direct=lambda p: p.moneyflow_ranking_stocks(),
            optional_live=True,
        ),
        ApiEntry(
            'moneyflow_ranking_stocks_sort', 'topics', '/v1/moneyflow/ranking/stocks/net', 'http',
            '个股资金榜（按排序映射路径）',
            (
                UsageCase(
                    'edge', 'sort=net path suffix',
                    lambda p: p.moneyflow_ranking_stocks(sort='net'),
                    '/v1/moneyflow/ranking/stocks/net',
                    live=False,
                ),
            ),
        ),
        _http('moneyflow_ranking_stocks_net', 'topics', '/v1/moneyflow/ranking/stocks/net',
              '个股净流入榜', direct=lambda p: p.moneyflow_ranking_stocks_net(), optional_live=True),
        _http('moneyflow_ranking_stocks_main', 'topics', '/v1/moneyflow/ranking/stocks/main',
              '主力榜', direct=lambda p: p.moneyflow_ranking_stocks_main(), optional_live=True),
        _http('moneyflow_ranking_stocks_retail', 'topics', '/v1/moneyflow/ranking/stocks/retail',
              '散户榜', direct=lambda p: p.moneyflow_ranking_stocks_retail(), optional_live=True),
        _http('moneyflow_ranking_snapshot', 'topics', '/v1/moneyflow/ranking/snapshot',
              '资金流快照', direct=lambda p: p.moneyflow_ranking_snapshot(), optional_live=True),
        _http(
            'moneyflow_ranking_live_stocks', 'topics', '/v1/moneyflow/ranking/live/stocks',
            '实时个股资金流排名（分页）',
            direct=lambda p: p.moneyflow_ranking_live_stocks(offset=0, limit=50, sort='net'),
            optional_live=True,
        ),
        ApiEntry(
            'moneyflow_live', 'topics', '/v1/moneyflow/live', 'http',
            '实时个股资金流向（按码 / 批量 / 全市场）',
            (
                UsageCase(
                    'direct', '单码',
                    lambda p: p.moneyflow_live(symbol=S),
                    '/v1/moneyflow/live',
                    expect_params={'symbol': S},
                    optional_live=True,
                ),
                UsageCase(
                    'edge', '全市场（推荐）',
                    lambda p: p.moneyflow_live(all=True),
                    '/v1/moneyflow/live',
                    expect_params={'all': 1},
                    live=False,
                ),
                UsageCase(
                    'edge', '批量',
                    lambda p: p.moneyflow_live(symbol=[S, SZ]),
                    '/v1/moneyflow/live',
                    expect_params={'symbol': f'{S},{SZ}'},
                    optional_live=True,
                ),
                UsageCase(
                    'escape', 'moneyflow_live via get(/v1/moneyflow/live)',
                    lambda p: p.get('/v1/moneyflow/live', {'all': 1}),
                    '/v1/moneyflow/live',
                    expect_params={'all': 1},
                    live=False,
                ),
            ),
        ),
        _http('suspend', 'topics', '/v1/suspend', '停复牌',
              direct=lambda p: p.suspend(), optional_live=True),
        _http('suspend_daily', 'topics', '/v1/suspend/daily', '停复牌日',
              direct=lambda p: p.suspend_daily(), optional_live=True),
        _http('suspend_dates', 'topics', '/v1/suspend/dates', '停复牌日期',
              direct=lambda p: p.suspend_dates()),
        _http(
            'suspend_stock', 'topics', '/v1/suspend/stock', '个股停复牌',
            direct=lambda p: p.suspend_stock(symbol=S),
            optional_live=True,
        ),
        _http('zfpg', 'topics', '/v1/zfpg', '增发配股',
              direct=lambda p: p.zfpg(), optional_live=True),
        _http('zfpg_daily', 'topics', '/v1/zfpg/daily', '增发配股日',
              direct=lambda p: p.zfpg_daily(date='2026-09-15'), optional_live=True),
        _http('zfpg_stock', 'topics', '/v1/zfpg/stock', '个股增发配股',
              direct=lambda p: p.zfpg_stock(symbol=S), optional_live=True),
        _http('zfpg_tabs', 'topics', '/v1/zfpg/tabs', '增发配股分类页签',
              direct=lambda p: p.zfpg_tabs()),
        _http('yjfp', 'topics', '/v1/yjfp', '业绩分配',
              direct=lambda p: p.yjfp(), optional_live=True),
        _http('yjfp_daily', 'topics', '/v1/yjfp/daily', '业绩分配日',
              direct=lambda p: p.yjfp_daily(date='2026-08-31'), optional_live=True),
        _http('yjfp_stock', 'topics', '/v1/yjfp/stock', '个股业绩分配',
              direct=lambda p: p.yjfp_stock(symbol=S), optional_live=True),
        _http('yjfp_tabs', 'topics', '/v1/yjfp/tabs', '业绩分配分类页签',
              direct=lambda p: p.yjfp_tabs()),
    ]

    # ---- catalog ----
    entries += [
        _http(
            'catalog_nodes', 'catalog', '/v1/catalog/nodes', '目录节点',
            direct=lambda p: p.catalog_nodes(limit=10),
            edge=lambda p: p.catalog_nodes(q='银行', leaves=True),
        ),
        _http(
            'catalog_node', 'catalog', '/v1/catalog/nodes/hsgs', '单节点',
            direct=lambda p: p.catalog_node('hsgs'),
            optional_live=True,
        ),
        _http(
            'catalog_node_children', 'catalog', '/v1/catalog/nodes/hsgs/children',
            '子节点', direct=lambda p: p.catalog_node_children('hsgs'), optional_live=True,
        ),
        _http(
            'catalog_node_members', 'catalog', '/v1/catalog/nodes/hangye_ZA01/members',
            '节点成分',
            direct=lambda p: p.catalog_node_members('hangye_ZA01', limit=5),
            optional_live=True,
        ),
        _http('catalog_plates', 'catalog', '/v1/catalog/plates', '板块目录',
              direct=lambda p: p.catalog_plates()),
        _http(
            'catalog_plate_members', 'catalog', '/v1/catalog/plates/38053809/members',
            '板块成分',
            direct=lambda p: p.catalog_plate_members(38053809),
            optional_live=True,
        ),
        _http('catalog_indices', 'catalog', '/v1/catalog/indices', '指数目录',
              direct=lambda p: p.catalog_indices()),
        _http(
            'catalog_index_members', 'catalog', '/v1/catalog/indices/399317/members',
            '指数成分',
            direct=lambda p: p.catalog_index_members('399317'),
            optional_live=True,
        ),
        _http(
            'catalog_stock', 'catalog', '/v1/catalog/stocks/600519.SS', '个股目录条目',
            direct=lambda p: p.catalog_stock(symbol=SH),
            alias=lambda p: p.catalog_stock(ks_code=S),
            optional_live=True,
        ),
    ]

    # ---- bond family ----
    _BOND_ZH = {
        'bond': '债券',
        'convertible': '可转债',
        'treasury': '国债',
        'enterprise': '企业债',
    }

    def _bond_family(kind: str, plural: str, kline_path: str, *, optional: bool = True) -> List[ApiEntry]:
        zh = _BOND_ZH[kind]
        out: List[ApiEntry] = []
        out.append(_http(kind, 'bond', f'/v1/{kind}', f'{zh}查询',
                         direct=lambda p, k=kind: getattr(p, k)(symbol=S), optional_live=optional))
        out.append(_http(f'{kind}_profile', 'bond', f'/v1/{kind}/profile', f'{zh}档案',
                         direct=lambda p, k=kind: getattr(p, f'{k}_profile')(symbol=S), optional_live=optional))
        out.append(_http(plural, 'bond', f'/v1/{plural}', f'{zh}列表',
                         direct=lambda p, pl=plural: getattr(p, pl)(limit=5), optional_live=optional))
        out.append(_http(f'{kind}_boards', 'bond', f'/v1/{kind}/boards', f'{zh}板块列表',
                         direct=lambda p, k=kind: getattr(p, f'{k}_boards')(), optional_live=optional))
        out.append(_http(f'{kind}_board', 'bond', f'/v1/{kind}/boards/default', f'{zh}单板块详情',
                         direct=lambda p, k=kind: getattr(p, f'{k}_board')('default'), optional_live=True))
        out.append(_http(f'{kind}_board_members', 'bond', f'/v1/{kind}/boards/default/members',
                         f'{zh}板块成分',
                         direct=lambda p, k=kind: getattr(p, f'{k}_board_members')('default'),
                         optional_live=True))
        out.append(_http(f'{kind}_realtime', 'bond', f'/v1/{kind}/realtime', f'{zh}实时行情',
                         direct=lambda p, k=kind: getattr(p, f'{k}_realtime')(symbol=S),
                         optional_live=optional))
        out.append(_http(f'{kind}_trend', 'bond', f'/v1/{kind}/trend', f'{zh}分时',
                         direct=lambda p, k=kind: getattr(p, f'{k}_trend')(symbol=S),
                         optional_live=optional))
        out.append(_http(f'{kind}_kline', 'bond', kline_path, f'{zh}K线',
                         direct=lambda p, k=kind: getattr(p, f'{k}_kline')(
                             symbol=S, period=86400, count=2
                         ),
                         optional_live=optional))
        return out

    entries += _bond_family('bond', 'bonds', '/v1/bond/kline')
    entries += _bond_family('convertible', 'convertibles', '/v2/convertible/kline')
    entries.append(
        _http(
            'convertible_auction', 'bond', '/v1/convertible/auction', '可转债竞价',
            direct=lambda p: p.convertible_auction(symbol=S), optional_live=True,
        )
    )
    entries.append(
        ApiEntry(
            'convertible_auction_v2', 'bond', '/v2/convertible/auction', 'http',
            '可转债竞价紧凑格式（一般用 all=True 拉全市场）',
            (
                UsageCase(
                    'direct', '全市场（推荐）',
                    lambda p: p.convertible_auction_v2(all=True),
                    '/v2/convertible/auction',
                    expect_params={'all': 1},
                    live=False,
                ),
                UsageCase(
                    'edge', '指定标的',
                    lambda p: p.convertible_auction_v2(symbol=S),
                    '/v2/convertible/auction',
                    expect_params={'symbol': S},
                    optional_live=True,
                ),
                UsageCase(
                    'escape', 'convertible_auction_v2 via get',
                    lambda p: p.get('/v2/convertible/auction'),
                    '/v2/convertible/auction', live=False,
                ),
            ),
        )
    )
    entries += _bond_family('treasury', 'treasuries', '/v1/treasury/kline')
    entries += _bond_family('enterprise', 'enterprises', '/v1/enterprise/kline')

    # ---- extended ----
    entries += [
        _http(
            'metal_realtime', 'extended', '/v1/metal/realtime', '贵金属实时',
            direct=lambda p: p.metal_realtime(),
            alias=lambda p: p.metal_realtime(symbols='XAUUSD'),
            edge=lambda p: p.metal_realtime(symbol='XAUUSD'),
            expect_params_alias={'symbols': 'XAUUSD'},
            optional_live=True,
        ),
        _http(
            'metal_kline', 'extended', '/v2/metal/kline', '贵金属K线',
            direct=lambda p: p.metal_kline(symbol='XAUUSD', period=86400, count=2),
            expect_params_direct={'symbol': 'XAUUSD', 'period': 86400, 'count': 2},
            optional_live=True,
        ),
        _http('metal_physical_brands', 'extended', '/v1/metal/physical/brands',
              '实物金品牌', direct=lambda p: p.metal_physical_brands(), optional_live=True),
        _http('metal_physical_products', 'extended', '/v1/metal/physical/products',
              '实物金产品', direct=lambda p: p.metal_physical_products(), optional_live=True),
        _http('metal_physical_prices', 'extended', '/v1/metal/physical/prices',
              '实物金报价', direct=lambda p: p.metal_physical_prices(), optional_live=True),
        _http(
            'futures_realtime', 'extended', '/v1/futures/realtime', '期货实时',
            direct=lambda p: p.futures_realtime(),
            edge=lambda p: p.futures_realtime(symbol='rb2501'),
            expect_params_edge={'symbol': 'rb2501'},
            optional_live=True,
        ),
        _http(
            'futures_kline', 'extended', '/v2/futures/kline', '期货K线',
            direct=lambda p: p.futures_kline(symbol='rb2501', period=86400, count=2),
            expect_params_direct={'symbol': 'rb2501'},
            optional_live=True,
        ),
        ApiEntry(
            'futures_stream', 'extended', '/v1/futures/stream', 'sse',
            '期货推流',
            (UsageCase('direct', 'futures_stream',
                       lambda p: next(iter(p.futures_stream())),
                       '/v1/futures/stream', optional_live=True),),
        ),
        _http(
            'futures_v2_realtime', 'extended', '/v1/futures-v2/realtime', '期货二代实时',
            direct=lambda p: p.futures_v2_realtime(), optional_live=True,
        ),
        _http(
            'futures_v2_trend', 'extended', '/v1/futures-v2/trend', '期货二代分时',
            direct=lambda p: p.futures_v2_trend(symbol='rb2501'), optional_live=True,
        ),
        _http(
            'futures_v2_kline', 'extended', '/v2/futures-v2/kline', '期货二代K线',
            direct=lambda p: p.futures_v2_kline(symbol='rb2501', period=86400, count=2),
            optional_live=True,
        ),
        ApiEntry(
            'futures_v2_stream', 'extended', '/v1/futures-v2/stream', 'sse',
            '期货二代推流',
            (UsageCase('direct', 'futures_v2_stream',
                       lambda p: next(iter(p.futures_v2_stream())),
                       '/v1/futures-v2/stream', optional_live=True),),
        ),
        _http(
            'global_index_realtime', 'extended', '/v1/global-index/realtime', '全球指数实时',
            direct=lambda p: p.global_index_realtime(symbol='DJI'),
            expect_params_direct={'symbol': 'DJI'},
            optional_live=True,
        ),
        _http(
            'global_index_trend', 'extended', '/v1/global-index/trend', '全球指数分时',
            direct=lambda p: p.global_index_trend(symbol='DJI'), optional_live=True,
        ),
        _http(
            'global_index_kline', 'extended', '/v2/global-index/kline', '全球指数K线',
            direct=lambda p: p.global_index_kline(symbol='DJI', period=86400, count=2),
            optional_live=True,
        ),
        _http(
            'global_bond_realtime', 'extended', '/v1/global-bond/realtime', '全球债券实时',
            direct=lambda p: p.global_bond_realtime(symbol='US10Y'),
            expect_params_direct={'symbol': 'US10Y'},
            optional_live=True,
        ),
        _http(
            'global_bond_kline', 'extended', '/v2/global-bond/kline', '全球债券K线',
            direct=lambda p: p.global_bond_kline(symbol='US10Y', period=86400, count=2),
            optional_live=True,
        ),
        _http(
            'usstock_realtime', 'extended', '/v1/usstock/realtime', '美股实时',
            direct=lambda p: p.usstock_realtime(symbol='AAPL'),
            alias=lambda p: p.usstock_realtime(ks_code='AAPL.US'),
            expect_params_direct={'symbol': 'AAPL.US'},
            optional_live=True,
        ),
        _http(
            'usstock_trend', 'extended', '/v1/usstock/trend', '美股分时',
            direct=lambda p: p.usstock_trend(symbol='AAPL.US'), optional_live=True,
        ),
        _http(
            'usstock_kline', 'extended', '/v2/usstock/kline', '美股K线',
            direct=lambda p: p.usstock_kline(symbol='AAPL.US', period=86400, count=2),
            optional_live=True,
        ),
        _http(
            'hkstock_realtime', 'extended', '/v1/hkstock/realtime', '港股实时',
            direct=lambda p: p.hkstock_realtime(symbol='00700'),
            alias=lambda p: p.hkstock_realtime(ks_code='HK00700'),
            expect_params_direct={'symbol': '00700.HK'},
            optional_live=True,
        ),
        _http(
            'hkstock_trend', 'extended', '/v1/hkstock/trend', '港股分时',
            direct=lambda p: p.hkstock_trend(symbol='00700.HK'),
            edge=lambda p: p.hkstock_trend(symbol='00700.HK', day=5),
            optional_live=True,
        ),
        _http(
            'hkstock_kline', 'extended', '/v2/hkstock/kline', '港股K线',
            direct=lambda p: p.hkstock_kline(
                symbol='00700.HK', period=86400, count=2, adjust_type='none',
            ),
            optional_live=True,
        ),
        _http(
            'plate_realtime', 'extended', '/v1/plate/realtime', '板块实时',
            direct=lambda p: p.plate_realtime(plate_id=38053809),
            edge=lambda p: p.plate_realtime(plate_id=[38053809, 1]),
            expect_params_direct={'plate_id': 38053809},
            expect_params_edge={'plate_id': '38053809,1'},
            optional_live=True,
        ),
        _http(
            'plate_trend', 'extended', '/v1/plate/trend', '板块分时',
            direct=lambda p: p.plate_trend(38053809), optional_live=True,
        ),
        _http(
            'plate_kline', 'extended', '/v2/plate/kline', '板块K线',
            direct=lambda p: p.plate_kline(38053809, period=86400, count=2), optional_live=True,
        ),
        _http(
            'plate_moneyflow', 'extended', '/v1/plate/moneyflow', '板块资金流',
            direct=lambda p: p.plate_moneyflow(38053809), optional_live=True,
        ),
        _http(
            'plate_moneyflow_ranking', 'extended', '/v1/plate/moneyflow/ranking',
            '板块资金榜', direct=lambda p: p.plate_moneyflow_ranking(), optional_live=True,
        ),
    ]

    # ---- ws / level2 ----
    entries += [
        ApiEntry(
            'realtime_ws_url', 'ws', '/v1/realtime/ws', 'ws',
            '逐笔行情连接地址（仅生成地址）',
            (
                UsageCase('direct', 'realtime_ws_url',
                          lambda p: p.realtime_ws_url(symbol=S), '/v1/realtime/ws'),
                UsageCase('alias', 'realtime_ws_url ks_code',
                          lambda p: p.realtime_ws_url(ks_code=SH), '/v1/realtime/ws', live=False),
            ),
        ),
        ApiEntry(
            'futures_ws_url', 'ws', '/v1/futures/ws', 'ws',
            '期货行情连接地址（仅生成地址）',
            (UsageCase('direct', 'futures_ws_url', lambda p: p.futures_ws_url(), '/v1/futures/ws'),),
        ),
        ApiEntry(
            'futures_v2_ws_url', 'ws', '/v1/futures-v2/ws', 'ws',
            '期货二代行情连接地址（仅生成地址）',
            (UsageCase('direct', 'futures_v2_ws_url',
                       lambda p: p.futures_v2_ws_url(), '/v1/futures-v2/ws'),),
        ),
        ApiEntry(
            'realtime_ws', 'ws', '/v1/realtime/ws', 'ws',
            '逐笔行情订阅',
            (
                UsageCase(
                    'direct', 'realtime_ws recv one',
                    lambda p: _ws_one(p.realtime_ws(symbol=S, timeout=10)),
                    '/v1/realtime/ws', optional_live=True,
                ),
            ),
        ),
        ApiEntry(
            'futures_ws', 'ws', '/v1/futures/ws', 'ws',
            '期货行情订阅',
            (
                UsageCase(
                    'direct', 'futures_ws',
                    lambda p: _ws_one(p.futures_ws(symbol='rb2501', timeout=10)),
                    '/v1/futures/ws', optional_live=True,
                ),
            ),
        ),
        ApiEntry(
            'futures_v2_ws', 'ws', '/v1/futures-v2/ws', 'ws',
            '期货二代行情订阅',
            (
                UsageCase(
                    'direct', 'futures_v2_ws',
                    lambda p: _ws_one(p.futures_v2_ws(symbol='rb2501', timeout=10)),
                    '/v1/futures-v2/ws', optional_live=True,
                ),
            ),
        ),
        ApiEntry(
            'level2', 'ws', 'pro.level2', 'local',
            'Level2 行情（depth / orders / trades / entrust）',
            (
                UsageCase(
                    'direct', 'level2 depth+trades+entrust',
                    lambda p: _l2_one(p),
                    optional_live=True,
                ),
            ),
        ),
    ]

    # ---- client helpers / factories ----
    entries.append(
        ApiEntry(
            'refresh_limits', 'core', '/v1/me', 'helper',
            '刷新限额缓存',
            (UsageCase('direct', 'refresh_limits', lambda p: p.refresh_limits(), '/v1/me'),),
        )
    )
    entries.append(
        ApiEntry(
            'get_escape', 'core', '/v1/health', 'helper',
            '通用请求',
            (
                UsageCase('escape', 'get /v1/health',
                          lambda p: p.get('/v1/health', auth=False), '/v1/health'),
            ),
        )
    )

    return entries


def _ws_one(feed: Any) -> Any:
    with feed:
        for i, msg in enumerate(feed):
            return msg
            if i > 20:
                break
    raise AssertionError('no ws message')


def _l2_one(pro: Any) -> Any:
    from klineshare.level2 import ensure_ks_live

    binary = ensure_ks_live(download=True, api_base=pro.base_url)
    with pro.level2(
        symbol='600519.SS',
        channels='depth,trades,entrust',
        binary=str(binary),
        download=False,
        run_for=8.0,
    ) as feed:
        for i, msg in enumerate(feed):
            return msg
            if i > 50:
                break
    raise AssertionError('no level2 message')


def live_cases(matrix: Optional[List[ApiEntry]] = None) -> List[tuple]:
    """Yield (entry_name, case) for live smoke."""
    out = []
    for entry in matrix or build_matrix():
        for case in entry.cases:
            if case.live and case.style in ('direct',):
                out.append((entry, case))
    return out


def mock_cases(matrix: Optional[List[ApiEntry]] = None) -> List[tuple]:
    """All http cases with expect_path for unit tests."""
    out = []
    for entry in matrix or build_matrix():
        if entry.kind not in ('http', 'text', 'helper'):
            continue
        for case in entry.cases:
            if case.expect_path and case.style != 'escape':
                out.append((entry, case))
            elif case.style == 'escape' and case.expect_path:
                out.append((entry, case))
    return out
