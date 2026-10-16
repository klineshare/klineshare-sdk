"""Extended markets: metal, futures, global index/bond, US stock, plate."""

from __future__ import annotations

from typing import Any, Iterable, Optional, Union

from klineshare._params import kline_page_timestamp
from klineshare.symbols import normalize_hk_symbol


class ExtendedEndpoints:
    """Mixin: extended market HTTP (+ SSE) endpoints."""

    # --------------------------------------------------------------- metal
    def metal_realtime(
        self,
        symbol: Optional[Union[str, Iterable[str]]] = None,
        *,
        symbols: Optional[Union[str, Iterable[str]]] = None,
        ks_code: Optional[Union[str, Iterable[str]]] = None,
        **opts: Any,
    ) -> Any:
        """贵金属实时 ``GET /v1/metal/realtime``（``symbol`` / ``symbols``）。"""
        raw = symbols if symbols is not None else symbol
        params = self._with_symbol({}, symbol=raw, ks_code=ks_code,
            normalize=False)
        # API also accepts ``symbols``
        if params.get('symbol') is not None:
            params['symbols'] = params.pop('symbol')
        return self._get('/v1/metal/realtime', params, **opts)

    def metal_kline(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        period: Optional[int] = None,
        count: Optional[int] = None,
        timestamp: Optional[int] = None,
        **opts: Any,
    ) -> Any:
        """贵金属 K 线 ``GET /v2/metal/kline``。"""
        params = self._with_symbol(
            {
                'period': period,
                'count': count,
                'timestamp': kline_page_timestamp(timestamp),
            },
            symbol=symbol,
            ks_code=ks_code,
            normalize=False)
        return self._get('/v2/metal/kline', params, **opts)

    def metal_physical_brands(self, *, keyword: Optional[str] = None, **opts: Any) -> Any:
        return self._get('/v1/metal/physical/brands', {'keyword': keyword}, **opts)

    def metal_physical_products(
        self,
        *,
        brand: Optional[str] = None,
        keyword: Optional[str] = None,
        **opts: Any,
    ) -> Any:
        return self._get(
            '/v1/metal/physical/products',
            {'brand': brand, 'keyword': keyword},
            **opts,
        )

    def metal_physical_prices(
        self,
        *,
        date: Optional[str] = None,
        brand: Optional[str] = None,
        product: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **opts: Any,
    ) -> Any:
        return self._get(
            '/v1/metal/physical/prices',
            {
                'date': date,
                'brand': brand,
                'product': product,
                'start_date': start_date,
                'end_date': end_date,
            },
            **opts,
        )

    # ------------------------------------------------------------- futures
    def futures_realtime(
        self,
        symbol: Optional[Union[str, Iterable[str]]] = None,
        *,
        ks_code: Optional[Union[str, Iterable[str]]] = None,
        **opts: Any,
    ) -> Any:
        params = self._with_symbol({}, symbol=symbol, ks_code=ks_code,
            normalize=False)
        return self._get('/v1/futures/realtime', params, **opts)

    def futures_kline(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        period: Optional[int] = None,
        count: Optional[int] = None,
        timestamp: Optional[int] = None,
        **opts: Any,
    ) -> Any:
        params = self._with_symbol(
            {
                'period': period,
                'count': count,
                'timestamp': kline_page_timestamp(timestamp),
            },
            symbol=symbol,
            ks_code=ks_code,
            normalize=False)
        return self._get('/v2/futures/kline', params, **opts)

    def futures_stream(self, **opts: Any) -> Any:
        """国内期货推送 SSE ``GET /v1/futures/stream``。"""
        return self.stream('/v1/futures/stream', **opts)

    def futures_v2_realtime(
        self,
        symbol: Optional[Union[str, Iterable[str]]] = None,
        *,
        ks_code: Optional[Union[str, Iterable[str]]] = None,
        **opts: Any,
    ) -> Any:
        params = self._with_symbol({}, symbol=symbol, ks_code=ks_code,
            normalize=False)
        return self._get('/v1/futures-v2/realtime', params, **opts)

    def futures_v2_trend(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        date: Optional[str] = None,
        **opts: Any,
    ) -> Any:
        params = self._with_symbol({'date': date}, symbol=symbol, ks_code=ks_code,
            normalize=False)
        return self._get('/v1/futures-v2/trend', params, **opts)

    def futures_v2_kline(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        period: Optional[int] = None,
        count: Optional[int] = None,
        timestamp: Optional[int] = None,
        **opts: Any,
    ) -> Any:
        params = self._with_symbol(
            {
                'period': period,
                'count': count,
                'timestamp': kline_page_timestamp(timestamp),
            },
            symbol=symbol,
            ks_code=ks_code,
            normalize=False)
        return self._get('/v2/futures-v2/kline', params, **opts)

    def futures_v2_stream(self, **opts: Any) -> Any:
        return self.stream('/v1/futures-v2/stream', **opts)

    # -------------------------------------------------------- global / US
    def global_index_realtime(
        self,
        symbol: Optional[Union[str, Iterable[str]]] = None,
        *,
        ks_code: Optional[Union[str, Iterable[str]]] = None,
        **opts: Any,
    ) -> Any:
        params = self._with_symbol({}, symbol=symbol, ks_code=ks_code,
            normalize=False)
        return self._get('/v1/global-index/realtime', params, **opts)

    def global_index_trend(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        date: Optional[str] = None,
        **opts: Any,
    ) -> Any:
        params = self._with_symbol({'date': date}, symbol=symbol, ks_code=ks_code,
            normalize=False)
        return self._get('/v1/global-index/trend', params, **opts)

    def global_index_kline(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        period: Optional[int] = None,
        count: Optional[int] = None,
        timestamp: Optional[int] = None,
        **opts: Any,
    ) -> Any:
        params = self._with_symbol(
            {
                'period': period,
                'count': count,
                'timestamp': kline_page_timestamp(timestamp),
            },
            symbol=symbol,
            ks_code=ks_code,
            normalize=False)
        return self._get('/v2/global-index/kline', params, **opts)

    def global_bond_realtime(
        self,
        symbol: Optional[Union[str, Iterable[str]]] = None,
        *,
        ks_code: Optional[Union[str, Iterable[str]]] = None,
        **opts: Any,
    ) -> Any:
        params = self._with_symbol({}, symbol=symbol, ks_code=ks_code,
            normalize=False)
        return self._get('/v1/global-bond/realtime', params, **opts)

    def global_bond_kline(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        period: Optional[int] = None,
        count: Optional[int] = None,
        timestamp: Optional[int] = None,
        **opts: Any,
    ) -> Any:
        params = self._with_symbol(
            {
                'period': period,
                'count': count,
                'timestamp': kline_page_timestamp(timestamp),
            },
            symbol=symbol,
            ks_code=ks_code,
            normalize=False)
        return self._get('/v2/global-bond/kline', params, **opts)

    def usstock_realtime(
        self,
        symbol: Optional[Union[str, Iterable[str]]] = None,
        *,
        ks_code: Optional[Union[str, Iterable[str]]] = None,
        **opts: Any,
    ) -> Any:
        params = self._with_symbol({}, symbol=symbol, ks_code=ks_code)
        return self._get('/v1/usstock/realtime', params, **opts)

    def usstock_trend(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        date: Optional[str] = None,
        day: Optional[int] = None,
        **opts: Any,
    ) -> Any:
        params = self._with_symbol(
            {'date': date, 'day': day},
            symbol=symbol,
            ks_code=ks_code,
        )
        return self._get('/v1/usstock/trend', params, **opts)

    def usstock_kline(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        period: Optional[int] = None,
        adjust_type: Optional[str] = None,
        count: Optional[int] = None,
        timestamp: Optional[int] = None,
        **opts: Any,
    ) -> Any:
        params = self._with_symbol(
            {
                'period': period,
                'adjust_type': adjust_type,
                'count': count,
                'timestamp': kline_page_timestamp(timestamp),
            },
            symbol=symbol,
            ks_code=ks_code,
        )
        return self._get('/v2/usstock/kline', params, **opts)

    def hkstock_realtime(
        self,
        symbol: Optional[Union[str, Iterable[str]]] = None,
        *,
        ks_code: Optional[Union[str, Iterable[str]]] = None,
        **opts: Any,
    ) -> Any:
        """港股实时 ``GET /v1/hkstock/realtime``（scope ``hkstock_realtime``）。"""
        params = self._with_symbol(
            {},
            symbol=symbol,
            ks_code=ks_code,
            normalizer=normalize_hk_symbol,
        )
        return self._get('/v1/hkstock/realtime', params, **opts)

    def hkstock_trend(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        date: Optional[str] = None,
        day: Optional[int] = None,
        **opts: Any,
    ) -> Any:
        """港股分时 ``GET /v1/hkstock/trend``；可选 ``day=1|5``。"""
        params = self._with_symbol(
            {'date': date, 'day': day},
            symbol=symbol,
            ks_code=ks_code,
            normalizer=normalize_hk_symbol,
        )
        return self._get('/v1/hkstock/trend', params, **opts)

    def hkstock_kline(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        period: Optional[int] = None,
        adjust_type: Optional[str] = None,
        count: Optional[int] = None,
        timestamp: Optional[int] = None,
        **opts: Any,
    ) -> Any:
        """港股 K 线 ``GET /v2/hkstock/kline``。暂仅 ``adjust_type=none``；``count``≤1800。"""
        params = self._with_symbol(
            {
                'period': period,
                'adjust_type': adjust_type,
                'count': count,
                'timestamp': kline_page_timestamp(timestamp),
            },
            symbol=symbol,
            ks_code=ks_code,
            normalizer=normalize_hk_symbol,
        )
        return self._get('/v2/hkstock/kline', params, **opts)

    # --------------------------------------------------------------- plate
    def plate_realtime(
        self,
        plate_id: Optional[Union[str, int, Iterable[Any]]] = None,
        **opts: Any,
    ) -> Any:
        params: dict = {}
        if plate_id is not None:
            if isinstance(plate_id, (list, tuple)):
                params['plate_id'] = ','.join(str(x) for x in plate_id)
            else:
                params['plate_id'] = plate_id
        return self._get('/v1/plate/realtime', params, **opts)

    def plate_trend(self, plate_id: Union[str, int], *, date: Optional[str] = None, **opts: Any) -> Any:
        return self._get(
            '/v1/plate/trend',
            {'plate_id': plate_id, 'date': date},
            **opts,
        )

    def plate_kline(
        self,
        plate_id: Union[str, int],
        *,
        period: Optional[int] = None,
        count: Optional[int] = None,
        timestamp: Optional[int] = None,
        **opts: Any,
    ) -> Any:
        return self._get(
            '/v2/plate/kline',
            {
                'plate_id': plate_id,
                'period': period,
                'count': count,
                'timestamp': kline_page_timestamp(timestamp),
            },
            **opts,
        )

    def plate_moneyflow(self, plate_id: Union[str, int], **opts: Any) -> Any:
        return self._get('/v1/plate/moneyflow', {'plate_id': plate_id}, **opts)

    def plate_moneyflow_ranking(self, **opts: Any) -> Any:
        return self._get('/v1/plate/moneyflow/ranking', **opts)
