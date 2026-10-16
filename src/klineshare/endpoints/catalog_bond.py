"""Catalog and bond family endpoints (bond / convertible / treasury / enterprise)."""

from __future__ import annotations

from typing import Any, Iterable, Optional, Union

from klineshare._params import DEFAULT_KLINE_FORMAT, kline_page_timestamp, with_kline_format
from klineshare.symbols import normalize_symbol


class CatalogBondEndpoints:
    """Mixin: catalog + bond-family HTTP endpoints."""

    # ------------------------------------------------------------- catalog
    def catalog_nodes(
        self,
        *,
        market: Optional[str] = None,
        category: Optional[str] = None,
        q: Optional[str] = None,
        keyword: Optional[str] = None,
        parent: Optional[str] = None,
        leaves: Optional[bool] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        **opts: Any,
    ) -> Any:
        return self._get(
            '/v1/catalog/nodes',
            {
                'market': market,
                'category': category,
                'q': q,
                'keyword': keyword,
                'parent': parent,
                'leaves': leaves,
                'limit': limit,
                'offset': offset,
            },
            **opts,
        )

    def catalog_node(self, node: str, **opts: Any) -> Any:
        return self._get(f'/v1/catalog/nodes/{node}', **opts)

    def catalog_node_children(self, node: str, **opts: Any) -> Any:
        return self._get(f'/v1/catalog/nodes/{node}/children', **opts)

    def catalog_node_members(
        self,
        node: str,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        **opts: Any,
    ) -> Any:
        return self._get(
            f'/v1/catalog/nodes/{node}/members',
            {'limit': limit, 'offset': offset},
            **opts,
        )

    def catalog_plates(
        self,
        *,
        type: Optional[str] = None,
        q: Optional[str] = None,
        **opts: Any,
    ) -> Any:
        return self._get('/v1/catalog/plates', {'type': type, 'q': q}, **opts)

    def catalog_plate_members(
        self,
        plate_id: str,
        *,
        include_desc: Optional[bool] = None,
        **opts: Any,
    ) -> Any:
        return self._get(
            f'/v1/catalog/plates/{plate_id}/members',
            {'include_desc': include_desc},
            **opts,
        )

    def catalog_indices(self, **opts: Any) -> Any:
        return self._get('/v1/catalog/indices', **opts)

    def catalog_index_members(self, code: str, **opts: Any) -> Any:
        return self._get(f'/v1/catalog/indices/{code}/members', **opts)

    def catalog_stock(
        self,
        symbol: Optional[str] = None,
        *,
        ks_code: Optional[str] = None,
        **opts: Any,
    ) -> Any:
        params = self._with_symbol({}, symbol=symbol, ks_code=ks_code)
        sym = params.get('symbol') or ''
        if not sym:
            raise ValueError('catalog_stock 需要 symbol / ks_code')
        return self._get(f'/v1/catalog/stocks/{normalize_symbol(str(sym))}', **opts)

    # ---- bond family helpers (prefix: bond|convertible|treasury|enterprise)

    def _bond_lookup(self, prefix: str, symbol=None, *, ks_code=None, **opts: Any) -> Any:
        params = self._with_symbol({}, symbol=symbol, ks_code=ks_code)
        return self._get(f'/v1/{prefix}', params, **opts)

    def _bond_profile(self, prefix: str, symbol=None, *, ks_code=None, **opts: Any) -> Any:
        params = self._with_symbol({}, symbol=symbol, ks_code=ks_code)
        return self._get(f'/v1/{prefix}/profile', params, **opts)

    def _bond_list(self, plural: str, *, keyword=None, limit=None, **opts: Any) -> Any:
        return self._get(f'/v1/{plural}', {'keyword': keyword, 'limit': limit}, **opts)

    def _bond_boards(self, prefix: str, **opts: Any) -> Any:
        return self._get(f'/v1/{prefix}/boards', **opts)

    def _bond_board(self, prefix: str, board: str, **opts: Any) -> Any:
        return self._get(f'/v1/{prefix}/boards/{board}', **opts)

    def _bond_board_members(self, prefix: str, board: str, **opts: Any) -> Any:
        return self._get(f'/v1/{prefix}/boards/{board}/members', **opts)

    def _bond_realtime(self, prefix: str, symbol=None, *, ks_code=None, **opts: Any) -> Any:
        params = self._with_symbol({}, symbol=symbol, ks_code=ks_code)
        return self._get(f'/v1/{prefix}/realtime', params, **opts)

    def _bond_trend(
        self, prefix: str, symbol=None, *, ks_code=None, date=None, **opts: Any
    ) -> Any:
        params = self._with_symbol({'date': date}, symbol=symbol, ks_code=ks_code)
        return self._get(f'/v1/{prefix}/trend', params, **opts)

    def _bond_kline(
        self,
        path: str,
        symbol=None,
        *,
        ks_code=None,
        period=None,
        adjust_type=None,
        count=None,
        timestamp=None,
        source=None,
        format=DEFAULT_KLINE_FORMAT,
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
        return self._get(path, params, **opts)

    # ---------------------------------------------------------------- bond (compat alias, any kind)
    def bond(self, symbol=None, *, ks_code=None, **opts: Any) -> Any:
        return self._bond_lookup('bond', symbol, ks_code=ks_code, **opts)

    def bond_profile(self, symbol=None, *, ks_code=None, **opts: Any) -> Any:
        return self._bond_profile('bond', symbol, ks_code=ks_code, **opts)

    def bonds(self, *, keyword=None, limit=None, **opts: Any) -> Any:
        return self._bond_list('bonds', keyword=keyword, limit=limit, **opts)

    def bond_boards(self, **opts: Any) -> Any:
        return self._bond_boards('bond', **opts)

    def bond_board(self, board: str, **opts: Any) -> Any:
        return self._bond_board('bond', board, **opts)

    def bond_board_members(self, board: str, **opts: Any) -> Any:
        return self._bond_board_members('bond', board, **opts)

    def bond_realtime(self, symbol=None, *, ks_code=None, **opts: Any) -> Any:
        return self._bond_realtime('bond', symbol, ks_code=ks_code, **opts)

    def bond_trend(self, symbol=None, *, ks_code=None, date=None, **opts: Any) -> Any:
        return self._bond_trend('bond', symbol, ks_code=ks_code, date=date, **opts)

    def bond_kline(self, symbol=None, *, ks_code=None, **opts: Any) -> Any:
        """兼容别名；可转债请用 ``convertible_kline``（/v2）。"""
        return self._bond_kline('/v1/bond/kline', symbol, ks_code=ks_code, **opts)

    # ---------------------------------------------------------- convertible
    def convertible(self, symbol=None, *, ks_code=None, **opts: Any) -> Any:
        return self._bond_lookup('convertible', symbol, ks_code=ks_code, **opts)

    def convertible_profile(self, symbol=None, *, ks_code=None, **opts: Any) -> Any:
        return self._bond_profile('convertible', symbol, ks_code=ks_code, **opts)

    def convertibles(self, *, keyword=None, limit=None, **opts: Any) -> Any:
        return self._bond_list('convertibles', keyword=keyword, limit=limit, **opts)

    def convertible_boards(self, **opts: Any) -> Any:
        return self._bond_boards('convertible', **opts)

    def convertible_board(self, board: str, **opts: Any) -> Any:
        return self._bond_board('convertible', board, **opts)

    def convertible_board_members(self, board: str, **opts: Any) -> Any:
        return self._bond_board_members('convertible', board, **opts)

    def convertible_realtime(self, symbol=None, *, ks_code=None, **opts: Any) -> Any:
        return self._bond_realtime('convertible', symbol, ks_code=ks_code, **opts)

    def convertible_trend(self, symbol=None, *, ks_code=None, date=None, **opts: Any) -> Any:
        return self._bond_trend('convertible', symbol, ks_code=ks_code, date=date, **opts)

    def convertible_kline(self, symbol=None, *, ks_code=None, **opts: Any) -> Any:
        """可转债 K 线 ``GET /v2/convertible/kline``。"""
        return self._bond_kline('/v2/convertible/kline', symbol, ks_code=ks_code, **opts)

    def convertible_auction(self, symbol=None, *, ks_code=None, **opts: Any) -> Any:
        params = self._with_symbol({}, symbol=symbol, ks_code=ks_code)
        return self._get('/v1/convertible/auction', params, **opts)

    def convertible_auction_v2(
        self,
        symbol: Optional[Union[str, Iterable[str]]] = None,
        *,
        ks_code: Optional[Union[str, Iterable[str]]] = None,
        all: Optional[bool] = None,
        **opts: Any,
    ) -> Any:
        """可转债竞价 compact ``GET /v2/convertible/auction``。

        一般用法是 ``all=True`` 拉全市场；也可传 ``symbol`` 指定标的。
        """
        params = self._with_symbol({'all': 1 if all else None}, symbol=symbol, ks_code=ks_code)
        return self._get('/v2/convertible/auction', params, **opts)

    # ------------------------------------------------------------ treasury
    def treasury(self, symbol=None, *, ks_code=None, **opts: Any) -> Any:
        return self._bond_lookup('treasury', symbol, ks_code=ks_code, **opts)

    def treasury_profile(self, symbol=None, *, ks_code=None, **opts: Any) -> Any:
        return self._bond_profile('treasury', symbol, ks_code=ks_code, **opts)

    def treasuries(self, *, keyword=None, limit=None, **opts: Any) -> Any:
        return self._bond_list('treasuries', keyword=keyword, limit=limit, **opts)

    def treasury_boards(self, **opts: Any) -> Any:
        return self._bond_boards('treasury', **opts)

    def treasury_board(self, board: str, **opts: Any) -> Any:
        return self._bond_board('treasury', board, **opts)

    def treasury_board_members(self, board: str, **opts: Any) -> Any:
        return self._bond_board_members('treasury', board, **opts)

    def treasury_realtime(self, symbol=None, *, ks_code=None, **opts: Any) -> Any:
        return self._bond_realtime('treasury', symbol, ks_code=ks_code, **opts)

    def treasury_trend(self, symbol=None, *, ks_code=None, date=None, **opts: Any) -> Any:
        return self._bond_trend('treasury', symbol, ks_code=ks_code, date=date, **opts)

    def treasury_kline(self, symbol=None, *, ks_code=None, **opts: Any) -> Any:
        return self._bond_kline('/v1/treasury/kline', symbol, ks_code=ks_code, **opts)

    # ---------------------------------------------------------- enterprise
    def enterprise(self, symbol=None, *, ks_code=None, **opts: Any) -> Any:
        return self._bond_lookup('enterprise', symbol, ks_code=ks_code, **opts)

    def enterprise_profile(self, symbol=None, *, ks_code=None, **opts: Any) -> Any:
        return self._bond_profile('enterprise', symbol, ks_code=ks_code, **opts)

    def enterprises(self, *, keyword=None, limit=None, **opts: Any) -> Any:
        return self._bond_list('enterprises', keyword=keyword, limit=limit, **opts)

    def enterprise_boards(self, **opts: Any) -> Any:
        return self._bond_boards('enterprise', **opts)

    def enterprise_board(self, board: str, **opts: Any) -> Any:
        return self._bond_board('enterprise', board, **opts)

    def enterprise_board_members(self, board: str, **opts: Any) -> Any:
        return self._bond_board_members('enterprise', board, **opts)

    def enterprise_realtime(self, symbol=None, *, ks_code=None, **opts: Any) -> Any:
        return self._bond_realtime('enterprise', symbol, ks_code=ks_code, **opts)

    def enterprise_trend(self, symbol=None, *, ks_code=None, date=None, **opts: Any) -> Any:
        return self._bond_trend('enterprise', symbol, ks_code=ks_code, date=date, **opts)

    def enterprise_kline(self, symbol=None, *, ks_code=None, **opts: Any) -> Any:
        return self._bond_kline('/v1/enterprise/kline', symbol, ks_code=ks_code, **opts)
