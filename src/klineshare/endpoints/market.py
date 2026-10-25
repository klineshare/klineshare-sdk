"""Realtime, trend, kline, stock/corp/finance/calendar."""

from __future__ import annotations

from typing import Any, Iterable, Iterator, List, Optional, Union

from klineshare._params import DEFAULT_KLINE_FORMAT, kline_page_timestamp, with_kline_format


def _page_records(page: Any) -> List[dict]:
    """Normalize a kline page to list-of-dicts for cursor extraction."""
    if page is None:
        return []
    try:
        import pandas as pd

        if isinstance(page, pd.DataFrame):
            if page.empty:
                return []
            return page.to_dict('records')
    except ImportError:
        pass
    if isinstance(page, list):
        return [row for row in page if isinstance(row, dict)]
    return []


def _earliest_bar_timestamp(records: List[dict]) -> Optional[int]:
    stamps = []
    for row in records:
        ts = row.get('timestamp')
        if ts is None:
            continue
        try:
            stamps.append(int(ts))
        except (TypeError, ValueError):
            continue
    if not stamps:
        return None
    return min(stamps)


class MarketEndpoints:
    """Mixin: endpoint methods (expects Client helpers)."""

    def realtime(
        self,
        symbol: Optional[Union[str, Iterable[str]]] = None,
        *,
        ks_code: Optional[Union[str, Iterable[str]]] = None,
        include_valuation: Optional[bool] = None,
        include_depth: Optional[bool] = None,
        **opts: Any,
    ) -> Any:
        """
        沪深京 A 股实时行情 ``GET /v1/realtime``（北交所 ``*.BJ`` 与沪深同路径）。

        单次 symbol 数受套餐 ``max_realtime_symbols`` 限制（客户端 enforce 下超额会本地报错）。
        """
        params = self._with_symbol(
            {
                'include_valuation': include_valuation,
                'include_depth': include_depth,
            },
            symbol=symbol,
            ks_code=ks_code,
        )
        return self._get('/v1/realtime', params, **opts)

    def realtime_v2(
        self,
        symbol: Optional[Union[str, Iterable[str]]] = None,
        *,
        ks_code: Optional[Union[str, Iterable[str]]] = None,
        all: Optional[bool] = None,
        market: Optional[str] = None,
        include_valuation: Optional[bool] = None,
        include_depth: Optional[bool] = None,
        **opts: Any,
    ) -> Any:
        """全市场 compact 实时 ``GET /v2/realtime``（独立 scope ``realtime_v2``）。

        一般用法是 ``all=True``（可加 ``market='SS'|'SZ'|...``）一次拉全市场；
        也可传 ``symbol`` / ``ks_code`` 做指定标的或批量。返回默认展开为行 / DataFrame。
        """
        params = self._with_symbol(
            {
                'all': 1 if all else None,
                'market': market,
                'include_valuation': include_valuation,
                'include_depth': include_depth,
            },
            symbol=symbol,
            ks_code=ks_code,
        )
        return self._get('/v2/realtime', params, **opts)

    def auction_v2(
        self,
        symbol: Optional[Union[str, Iterable[str]]] = None,
        *,
        ks_code: Optional[Union[str, Iterable[str]]] = None,
        all: Optional[bool] = None,
        market: Optional[str] = None,
        trade_date: Optional[str] = None,
        include_minutes: Optional[bool] = None,
        **opts: Any,
    ) -> Any:
        """集合竞价 compact ``GET /v2/auction``。

        一般用法是 ``all=True`` 拉全市场（可加 ``market`` / ``include_minutes``）；
        单标的场景也可传 ``symbol``。与 ``auction``（``/v1/auction`` 单标的分时）不同。
        """
        params = self._with_symbol(
            {
                'all': 1 if all else None,
                'market': market,
                'trade_date': trade_date,
                'include_minutes': include_minutes,
            },
            symbol=symbol,
            ks_code=ks_code,
        )
        return self._get('/v2/auction', params, **opts)

    def market_kline_v2(
        self,
        *,
        all: bool = True,
        market: Optional[str] = None,
        period: Optional[int] = None,
        count: Optional[int] = None,
        **opts: Any,
    ) -> Any:
        """全市场近端分钟 K compact ``GET /v2/market-kline``（独立 scope ``market_kline_v2``）。

        仅支持 ``all=True``（默认）；可加 ``market='SS'|'SZ'|'BJ'|'CN'``（不含美股）。
        ``period`` 当前仅 ``60``；``count`` 默认 2、上限 5。
        体量大，服务端强制 ``Accept-Encoding: gzip``（SDK Session 已默认协商）。
        返回默认展开为行（``bars`` 嵌套列表）/ DataFrame。
        """
        if not all:
            raise ValueError('market_kline_v2 仅支持 all=True')
        params = {
            'all': 1,
            'market': market,
            'period': period,
            'count': count,
        }
        return self._get('/v2/market-kline', params, **opts)

    def trend(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        date: Optional[str] = None,
        **opts: Any,
    ) -> Any:
        """分时图 ``GET /v1/trend``（每次仅 1 个 symbol）。"""
        params = self._with_symbol({'date': date}, symbol=symbol, ks_code=ks_code)
        return self._get('/v1/trend', params, **opts)

    def auction(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        **opts: Any,
    ) -> Any:
        """沪深京单票集合竞价分时 ``GET /v1/auction``。"""
        params = self._with_symbol({}, symbol=symbol, ks_code=ks_code)
        return self._get('/v1/auction', params, **opts)

    def kline(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        period: Optional[int] = None,
        adjust_type: Optional[str] = None,
        count: Optional[int] = None,
        timestamp: Optional[int] = None,
        indicators: Optional[str] = None,
        source: Optional[str] = None,
        batch: Optional[str] = None,
        format: Optional[str] = DEFAULT_KLINE_FORMAT,
        **opts: Any,
    ) -> Any:
        """
        K 线 ``GET /v2/kline``（默认 ``format=raw`` 极限体积分隔串，展开为行 / DataFrame）。

        ``format`` 默认 ``"raw"``；传 ``None`` 则不带该参数（服务端列式二维数组）。
        与 ``raw=True``（返回完整 JSON 信封、不 unwrap）无关。

        ``batch``:
          - ``multi``（默认）：多标的一次请求
          - ``single``：强制按标的拆成多次请求再合并
          - ``auto``：日线及以上且 ``标的数×count > kline_heavy_threshold`` 时按标的拆分
            （客户端启发式，减小单次响应体积；会多占 RPM）。``raw=True`` 时不拆分。
        """
        from klineshare.limits.quota import _split_symbols, should_split_kline_batch

        params = self._with_symbol(
            with_kline_format(
                {
                    'period': period,
                    'adjust_type': adjust_type,
                    'count': count,
                    'timestamp': kline_page_timestamp(timestamp),
                    'indicators': indicators,
                    'source': source,
                },
                format=format,
            ),
            symbol=symbol,
            ks_code=ks_code,
        )
        mode = (batch or getattr(self, 'kline_batch', None) or 'multi').strip().lower()
        syms = _split_symbols(params.get('symbol'))
        raw = bool(opts.get('raw'))
        threshold = int(getattr(self, 'kline_heavy_threshold', 3000))
        do_split = mode == 'single' or (
            mode == 'auto'
            and not raw
            and should_split_kline_batch(
                n_symbols=len(syms),
                period=params.get('period'),
                count=params.get('count'),
                threshold=threshold,
            )
        )
        if do_split and len(syms) >= 2:
            rows: List[Any] = []
            for sym in syms:
                one = dict(params)
                one['symbol'] = sym
                part = self._get('/v2/kline', one, **opts)
                if isinstance(part, list):
                    rows.extend(part)
                elif part is not None:
                    # DataFrame or unexpected — coerce via records helper
                    try:
                        import pandas as pd

                        if isinstance(part, pd.DataFrame):
                            rows.extend(part.to_dict('records'))
                            continue
                    except ImportError:
                        pass
                    rows.append(part)
            flag = opts.get('as_dataframe')
            if flag is None:
                flag = getattr(self, 'as_dataframe', None)
            from klineshare._result import maybe_frame

            return maybe_frame(rows, as_dataframe=flag)
        return self._get('/v2/kline', params, **opts)

    def iter_kline(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        period: Optional[int] = None,
        adjust_type: Optional[str] = None,
        count: Optional[int] = None,
        timestamp: Optional[int] = None,
        indicators: Optional[str] = None,
        source: Optional[str] = None,
        format: Optional[str] = DEFAULT_KLINE_FORMAT,
        max_pages: Optional[int] = None,
        **opts: Any,
    ) -> Iterator[Any]:
        """
        向更早时间翻页拉取 K 线，逐页 yield（与 ``kline`` 相同返回形态）。

        下一页 cursor = 本页最早一根 ``timestamp``（毫秒）减 1，经 SDK 换算为秒后请求。
        空页、或无法解析 cursor 时停止；``max_pages`` 可限制页数。每页仍走限额管线。
        """
        cursor = timestamp
        pages = 0
        while True:
            if max_pages is not None and pages >= max_pages:
                break
            page = self.kline(
                symbol=symbol,
                ks_code=ks_code,
                period=period,
                adjust_type=adjust_type,
                count=count,
                timestamp=cursor,
                indicators=indicators,
                source=source,
                format=format,
                **opts,
            )
            pages += 1
            records = _page_records(page)
            if not records:
                break
            yield page
            earliest = _earliest_bar_timestamp(records)
            if earliest is None:
                break
            next_cursor = earliest - 1
            if cursor is not None and kline_page_timestamp(next_cursor) == kline_page_timestamp(
                cursor
            ):
                break
            cursor = next_cursor
            if count is not None:
                try:
                    if len(records) < int(count):
                        break
                except (TypeError, ValueError):
                    pass

    def adjust_factors(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        adjust_type: Optional[str] = None,
        count: Optional[int] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        **opts: Any,
    ) -> Any:
        """复权因子 ``GET /v1/adjust-factors``（**不建议**；请改用 ``adjust_params``）。"""
        params = self._with_symbol(
            {
                'adjust_type': adjust_type,
                'count': count,
                'start': start,
                'end': end,
            },
            symbol=symbol,
            ks_code=ks_code,
        )
        return self._get('/v1/adjust-factors', params, **opts)

    def exrights(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        count: Optional[int] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        **opts: Any,
    ) -> Any:
        """除权除息 ``GET /v1/exrights``。"""
        params = self._with_symbol(
            {
                'count': count,
                'start': start,
                'end': end,
            },
            symbol=symbol,
            ks_code=ks_code,
        )
        return self._get('/v1/exrights', params, **opts)

    def adjust_params(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        adjust_type: Optional[str] = None,
        count: Optional[int] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        **opts: Any,
    ) -> Any:
        """复权参数 ``GET /v1/adjust-params``（**推荐**自行复权；affine：价=(原价×multiplier+addend)/10000）。"""
        params = self._with_symbol(
            {
                'adjust_type': adjust_type,
                'count': count,
                'start': start,
                'end': end,
            },
            symbol=symbol,
            ks_code=ks_code,
        )
        return self._get('/v1/adjust-params', params, **opts)

    def bj_trend(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        date: Optional[str] = None,
        **opts: Any,
    ) -> Any:
        params = self._with_symbol({'date': date}, symbol=symbol, ks_code=ks_code)
        return self._get('/v1/bj/trend', params, **opts)

    def bj_kline(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        period: Optional[int] = None,
        adjust_type: Optional[str] = None,
        count: Optional[int] = None,
        timestamp: Optional[int] = None,
        source: Optional[str] = None,
        format: Optional[str] = DEFAULT_KLINE_FORMAT,
        **opts: Any,
    ) -> Any:
        params = self._with_symbol(
            with_kline_format(
                {
                    'period': period,
                    'adjust_type': adjust_type,
                    'count': count,
                    'timestamp': kline_page_timestamp(timestamp),
                    'source': source,
                },
                format=format,
            ),
            symbol=symbol,
            ks_code=ks_code,
        )
        return self._get('/v1/bj/kline', params, **opts)

    def stock(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        **opts: Any,
    ) -> Any:
        params = self._with_symbol({}, symbol=symbol, ks_code=ks_code)
        return self._get('/v1/stock', params, **opts)

    def stocks(
        self,
        *,
        keyword: Optional[str] = None,
        market: Optional[str] = None,
        limit: Optional[int] = None,
        page: Optional[int] = None,
        num: Optional[int] = None,
        **opts: Any,
    ) -> Any:
        return self._get(
            '/v1/stocks',
            {
                'keyword': keyword,
                'market': market,
                'limit': limit,
                'page': page,
                'num': num,
            },
            **opts,
        )

    def corp(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        **opts: Any,
    ) -> Any:
        params = self._with_symbol({}, symbol=symbol, ks_code=ks_code)
        return self._get('/v1/corp', params, **opts)

    def finance_report(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        source: Optional[str] = None,
        periods: Optional[str] = None,
        year: Optional[Union[str, int]] = None,
        years: Optional[str] = None,
        period: Optional[str] = None,
        **opts: Any,
    ) -> Any:
        params = self._with_symbol(
            {
                'source': source,
                'periods': periods,
                'year': year,
                'years': years,
                'period': period,
            },
            symbol=symbol,
            ks_code=ks_code,
        )
        return self._get('/v1/finance/report', params, **opts)

    def calendar(
        self,
        *,
        date: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        window: Optional[str] = None,
        **opts: Any,
    ) -> Any:
        return self._get(
            '/v1/calendar',
            {'date': date, 'start': start, 'end': end, 'window': window},
            **opts,
        )
