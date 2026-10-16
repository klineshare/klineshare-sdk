"""Limit-up, LHB, moneyflow, streams, hot money."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Iterator, List, Optional, Union

from klineshare._params import kline_page_timestamp

class TopicsEndpoints:
    """Mixin: endpoint methods (expects Client helpers)."""

    # -------------------------------------------------------------- limit-up
    def limit_up(self, **opts: Any) -> Any:
        return self._get('/v1/limit-up', **opts)

    def limit_up_break(self, **opts: Any) -> Any:
        return self._get('/v1/limit-up/break', **opts)

    def limit_down(self, **opts: Any) -> Any:
        return self._get('/v1/limit-up/limit-down', **opts)

    def yesterday_limit_up(self, **opts: Any) -> Any:
        return self._get('/v1/limit-up/yesterday', **opts)

    def limit_up_ladder(self, **opts: Any) -> Any:
        return self._get('/v1/limit-up/ladder', **opts)

    def limit_up_plates_trending(
        self,
        *,
        limit: Optional[int] = None,
        field: Optional[str] = None,
        **opts: Any,
    ) -> Any:
        return self._get(
            '/v1/limit-up/plates/trending',
            {'limit': limit, 'field': field},
            **opts,
        )

    def limit_up_plates_industry(
        self,
        *,
        limit: Optional[int] = None,
        field: Optional[str] = None,
        **opts: Any,
    ) -> Any:
        return self._get(
            '/v1/limit-up/plates/industry',
            {'limit': limit, 'field': field},
            **opts,
        )

    def limit_up_plates_concept(
        self,
        *,
        limit: Optional[int] = None,
        field: Optional[str] = None,
        **opts: Any,
    ) -> Any:
        return self._get(
            '/v1/limit-up/plates/concept',
            {'limit': limit, 'field': field},
            **opts,
        )

    def limit_up_plates_style(
        self,
        *,
        limit: Optional[int] = None,
        field: Optional[str] = None,
        **opts: Any,
    ) -> Any:
        return self._get(
            '/v1/limit-up/plates/style',
            {'limit': limit, 'field': field},
            **opts,
        )

    def abnormal_events(
        self,
        *,
        count: Optional[int] = None,
        types: Optional[str] = None,
        kind: Optional[str] = None,
        timestamp: Optional[int] = None,
        **opts: Any,
    ) -> Any:
        return self._get(
            '/v1/abnormal-events',
            {
                'count': count,
                'types': types,
                'kind': kind,
                'timestamp': timestamp,
            },
            **opts,
        )

    def abnormal_events_stream(
        self,
        *,
        types: Optional[str] = None,
        kind: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Iterator[Dict[str, Any]]:
        return self.stream(
            '/v1/abnormal-events/stream',
            {'types': types, 'kind': kind},
            timeout=timeout,
        )

    def market_flash_stream(
        self,
        *,
        actions: Optional[str] = None,
        include_withdrawn: Optional[bool] = None,
        timeout: Optional[float] = None,
    ) -> Iterator[Dict[str, Any]]:
        return self.stream(
            '/v1/market-flash/stream',
            {'actions': actions, 'include_withdrawn': include_withdrawn},
            timeout=timeout,
        )

    # ----------------------------------------------------------------- lhb

    # ----------------------------------------------------------------- lhb
    def lhb_daily(
        self,
        *,
        date: Optional[str] = None,
        tradedate: Optional[str] = None,
        with_details: Optional[bool] = None,
        **opts: Any,
    ) -> Any:
        return self._get(
            '/v1/lhb/daily',
            {
                'date': date,
                'tradedate': tradedate,
                'with_details': with_details,
            },
            **opts,
        )

    def lhb_stock(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        bdate: Optional[str] = None,
        edate: Optional[str] = None,
        **opts: Any,
    ) -> Any:
        params = self._with_symbol(
            {'bdate': bdate, 'edate': edate},
            symbol=symbol,
            ks_code=ks_code,
        )
        return self._get('/v1/lhb/stock', params, **opts)

    def lhb(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        date: Optional[str] = None,
        bdate: Optional[str] = None,
        edate: Optional[str] = None,
        **opts: Any,
    ) -> Any:
        params = self._with_symbol(
            {'date': date, 'bdate': bdate, 'edate': edate},
            symbol=symbol,
            ks_code=ks_code,
        )
        return self._get('/v1/lhb', params, **opts)

    def lhb_dates(self, **opts: Any) -> Any:
        return self._get('/v1/lhb/dates', **opts)

    def lhb_stats(
        self,
        *,
        kind: Optional[str] = None,
        lastdays: Optional[int] = None,
        bdate: Optional[str] = None,
        edate: Optional[str] = None,
        page: Optional[int] = None,
        **opts: Any,
    ) -> Any:
        return self._get(
            '/v1/lhb/stats',
            {
                'kind': kind,
                'lastdays': lastdays,
                'bdate': bdate,
                'edate': edate,
                'page': page,
            },
            **opts,
        )

    def hot_money(
        self,
        *,
        name: Optional[str] = None,
        keyword: Optional[str] = None,
        q: Optional[str] = None,
        **opts: Any,
    ) -> Any:
        return self._get(
            '/v1/hot-money',
            {'name': name, 'keyword': keyword, 'q': q},
            **opts,
        )

    def hot_money_seat(
        self,
        *,
        broker: Optional[str] = None,
        seat: Optional[str] = None,
        **opts: Any,
    ) -> Any:
        return self._get(
            '/v1/hot-money/seat',
            {'broker': broker, 'seat': seat},
            **opts,
        )

    def hot_money_detail(
        self,
        *,
        name: Optional[str] = None,
        symbol: Optional[str] = None,
        ks_code: Optional[str] = None,
        **opts: Any,
    ) -> Any:
        """游资反查 ``GET /v1/hot-money/detail``。"""
        params = self._with_symbol({'name': name}, symbol=symbol, ks_code=ks_code)
        return self._get('/v1/hot-money/detail', params, **opts)

    def hot_money_stats(self, **opts: Any) -> Any:
        """游资统计 ``GET /v1/hot-money/stats``。"""
        return self._get('/v1/hot-money/stats', {}, **opts)

    # ----------------------------------------------------------- moneyflow
    def moneyflow_daily_trend(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        date: Optional[str] = None,
        bdate: Optional[str] = None,
        edate: Optional[str] = None,
        limit: Optional[int] = None,
        **opts: Any,
    ) -> Any:
        params = self._with_symbol(
            {'date': date, 'bdate': bdate, 'edate': edate, 'limit': limit},
            symbol=symbol,
            ks_code=ks_code,
        )
        return self._get('/v1/moneyflow/daily-trend', params, **opts)

    def moneyflow_stage(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        date: Optional[str] = None,
        bdate: Optional[str] = None,
        edate: Optional[str] = None,
        limit: Optional[int] = None,
        **opts: Any,
    ) -> Any:
        params = self._with_symbol(
            {'date': date, 'bdate': bdate, 'edate': edate, 'limit': limit},
            symbol=symbol,
            ks_code=ks_code,
        )
        return self._get('/v1/moneyflow/stage', params, **opts)

    def moneyflow_distribution(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        date: Optional[str] = None,
        bdate: Optional[str] = None,
        edate: Optional[str] = None,
        limit: Optional[int] = None,
        **opts: Any,
    ) -> Any:
        params = self._with_symbol(
            {'date': date, 'bdate': bdate, 'edate': edate, 'limit': limit},
            symbol=symbol,
            ks_code=ks_code,
        )
        return self._get('/v1/moneyflow/distribution', params, **opts)

    def moneyflow_ranking_boards(
        self,
        *,
        category: Optional[str] = None,
        **opts: Any,
    ) -> Any:
        return self._get(
            '/v1/moneyflow/ranking/boards',
            {'category': category},
            **opts,
        )

    def moneyflow_ranking_stocks(
        self,
        *,
        sort: Optional[str] = None,
        **opts: Any,
    ) -> Any:
        """兼容入口；精确榜单请用 ``moneyflow_ranking_stocks_net|main|retail``。"""
        path = '/v1/moneyflow/ranking/stocks'
        if sort in ('net', 'main', 'retail'):
            path = f'/v1/moneyflow/ranking/stocks/{sort}'
            return self._get(path, **opts)
        return self._get(path, {'sort': sort}, **opts)

    def moneyflow_ranking_stocks_net(self, **opts: Any) -> Any:
        return self._get('/v1/moneyflow/ranking/stocks/net', **opts)

    def moneyflow_ranking_stocks_main(self, **opts: Any) -> Any:
        return self._get('/v1/moneyflow/ranking/stocks/main', **opts)

    def moneyflow_ranking_stocks_retail(self, **opts: Any) -> Any:
        return self._get('/v1/moneyflow/ranking/stocks/retail', **opts)

    def moneyflow_ranking_snapshot(self, **opts: Any) -> Any:
        return self._get('/v1/moneyflow/ranking/snapshot', **opts)

    def moneyflow_ranking_live_stocks(
        self,
        *,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        sort: Optional[str] = None,
        order: Optional[str] = None,
        **opts: Any,
    ) -> Any:
        """实时个股资金流排名（分页）``GET /v1/moneyflow/ranking/live/stocks``。

        每次请求实时拉一页（非快照）；需 ``moneyflow``。``limit`` 默认 50、最大 100；
        ``sort`` 默认 ``net``（另有 ``in`` / ``out`` / ``net_5d`` / ``net_30d`` /
        ``price`` / ``change_percent`` / ``turnover``）；``order`` 为 ``desc``/``asc``。
        不支持 ``date`` / ``bdate`` / ``edate`` / ``capture_id``。
        """
        return self._get(
            '/v1/moneyflow/ranking/live/stocks',
            {
                'offset': offset,
                'limit': limit,
                'sort': sort,
                'order': order,
            },
            **opts,
        )

    def moneyflow_live(
        self,
        symbol: Optional[Union[str, Iterable[str]]] = None,
        *,
        ks_code: Optional[Union[str, Iterable[str]]] = None,
        all: Optional[bool] = None,
        **opts: Any,
    ) -> Any:
        """实时个股资金流向 ``GET /v1/moneyflow/live``。

        ``symbol`` 批量最多 200 只；或 ``all=True`` 拉沪深全市场（不含北交）。
        与 ``symbol`` 二选一。不支持 ``date`` / ``bdate`` / ``edate`` / ``capture_id``。
        """
        params = self._with_symbol(
            {'all': 1 if all else None},
            symbol=symbol,
            ks_code=ks_code,
        )
        return self._get('/v1/moneyflow/live', params, **opts)

    # ------------------------------------------------------------- suspend
    def suspend(self, **opts: Any) -> Any:
        return self._get('/v1/suspend', **opts)

    def suspend_daily(self, *, date: Optional[str] = None, **opts: Any) -> Any:
        return self._get('/v1/suspend/daily', {'date': date}, **opts)

    def suspend_dates(self, **opts: Any) -> Any:
        return self._get('/v1/suspend/dates', **opts)

    def suspend_stock(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        **opts: Any,
    ) -> Any:
        params = self._with_symbol({}, symbol=symbol, ks_code=ks_code)
        return self._get('/v1/suspend/stock', params, **opts)

    # ---------------------------------------------------------------- zfpg
    def zfpg(self, **opts: Any) -> Any:
        return self._get('/v1/zfpg', **opts)

    def zfpg_daily(self, *, date: Optional[str] = None, **opts: Any) -> Any:
        return self._get('/v1/zfpg/daily', {'date': date}, **opts)

    def zfpg_stock(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        **opts: Any,
    ) -> Any:
        params = self._with_symbol({}, symbol=symbol, ks_code=ks_code)
        return self._get('/v1/zfpg/stock', params, **opts)

    def zfpg_tabs(self, **opts: Any) -> Any:
        return self._get('/v1/zfpg/tabs', **opts)

    # ---------------------------------------------------------------- yjfp
    def yjfp(self, **opts: Any) -> Any:
        return self._get('/v1/yjfp', **opts)

    def yjfp_daily(self, *, date: Optional[str] = None, **opts: Any) -> Any:
        return self._get('/v1/yjfp/daily', {'date': date}, **opts)

    def yjfp_stock(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        **opts: Any,
    ) -> Any:
        params = self._with_symbol({}, symbol=symbol, ks_code=ks_code)
        return self._get('/v1/yjfp/stock', params, **opts)

    def yjfp_tabs(self, **opts: Any) -> Any:
        return self._get('/v1/yjfp/tabs', **opts)
