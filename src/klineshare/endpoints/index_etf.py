"""Index and ETF endpoints."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Iterator, List, Optional, Union

from klineshare._params import DEFAULT_KLINE_FORMAT, kline_page_timestamp, with_kline_format

class IndexEtfEndpoints:
    """Mixin: endpoint methods (expects Client helpers)."""

    # --------------------------------------------------------------- index
    def index_realtime(
        self,
        symbol: Optional[Union[str, Iterable[str]]] = None,
        *,
        ks_code: Optional[Union[str, Iterable[str]]] = None,
        include_valuation: Optional[bool] = None,
        include_depth: Optional[bool] = None,
        **opts: Any,
    ) -> Any:
        params = self._with_symbol(
            {
                'include_valuation': include_valuation,
                'include_depth': include_depth,
            },
            symbol=symbol,
            ks_code=ks_code,
        )
        return self._get('/v1/index/realtime', params, **opts)

    def index_trend(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        date: Optional[str] = None,
        **opts: Any,
    ) -> Any:
        params = self._with_symbol({'date': date}, symbol=symbol, ks_code=ks_code)
        return self._get('/v1/index/trend', params, **opts)

    def index_kline(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        period: Optional[int] = None,
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
                    'adjust_type': 'none',
                    'count': count,
                    'timestamp': kline_page_timestamp(timestamp),
                    'source': source,
                },
                format=format,
            ),
            symbol=symbol,
            ks_code=ks_code,
        )
        return self._get('/v2/index/kline', params, **opts)

    # ----------------------------------------------------------------- etf
    def etf(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        **opts: Any,
    ) -> Any:
        params = self._with_symbol({}, symbol=symbol, ks_code=ks_code)
        return self._get('/v1/etf', params, **opts)

    def etfs(
        self,
        *,
        keyword: Optional[str] = None,
        market: Optional[str] = None,
        limit: Optional[int] = None,
        **opts: Any,
    ) -> Any:
        return self._get(
            '/v1/etfs',
            {'keyword': keyword, 'market': market, 'limit': limit},
            **opts,
        )

    def etf_realtime(
        self,
        symbol: Optional[Union[str, Iterable[str]]] = None,
        *,
        ks_code: Optional[Union[str, Iterable[str]]] = None,
        include_valuation: Optional[bool] = None,
        include_depth: Optional[bool] = None,
        **opts: Any,
    ) -> Any:
        params = self._with_symbol(
            {
                'include_valuation': include_valuation,
                'include_depth': include_depth,
            },
            symbol=symbol,
            ks_code=ks_code,
        )
        return self._get('/v1/etf/realtime', params, **opts)

    def etf_trend(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        date: Optional[str] = None,
        **opts: Any,
    ) -> Any:
        params = self._with_symbol({'date': date}, symbol=symbol, ks_code=ks_code)
        return self._get('/v1/etf/trend', params, **opts)

    def etf_kline(
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
        return self._get('/v2/etf/kline', params, **opts)
