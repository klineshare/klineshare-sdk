"""Health, me, public catalog / schemas / docs."""

from __future__ import annotations

from typing import Any, Optional

class MetaEndpoints:
    """Mixin: endpoint methods (expects Client helpers)."""

    # --------------------------------------------------------------- meta
    def health(self, **opts: Any) -> Any:
        return self._get('/v1/health', auth=False, **opts)

    def me(self, **opts: Any) -> Any:
        """当前 Key 权限与限额 ``GET /v1/me``（也是客户端限额缓存的数据源）。"""
        return self._get('/v1/me', **opts)

    # ------------------------------------------------------------ realtime

    def public_indices(
        self,
        *,
        keyword: Optional[str] = None,
        listed: Optional[bool] = None,
        limit: Optional[int] = None,
        quote_ready: Optional[bool] = None,
        **opts: Any,
    ) -> Any:
        return self._get(
            '/public/v1/indices',
            {
                'keyword': keyword,
                'listed': listed,
                'limit': limit,
                'quote_ready': quote_ready,
            },
            auth=False,
            **opts,
        )

    def public_catalog(self, **opts: Any) -> Any:
        return self._get('/public/v1/catalog', auth=False, **opts)

    def public_metals(
        self,
        *,
        keyword: Optional[str] = None,
        group: Optional[str] = None,
        limit: Optional[int] = None,
        **opts: Any,
    ) -> Any:
        """贵金属公开清单 ``GET /public/v1/metals``。"""
        return self._get(
            '/public/v1/metals',
            {'keyword': keyword, 'group': group, 'limit': limit},
            auth=False,
            **opts,
        )

    def public_futures(
        self,
        *,
        exchange: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: Optional[int] = None,
        **opts: Any,
    ) -> Any:
        """国内期货 v1 公开清单 ``GET /public/v1/futures``。"""
        return self._get(
            '/public/v1/futures',
            {'exchange': exchange, 'keyword': keyword, 'limit': limit},
            auth=False,
            **opts,
        )

    def public_futures_v2(
        self,
        *,
        exchange: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: Optional[int] = None,
        **opts: Any,
    ) -> Any:
        """国内期货 v2 公开清单 ``GET /public/v1/futures-v2``。"""
        return self._get(
            '/public/v1/futures-v2',
            {'exchange': exchange, 'keyword': keyword, 'limit': limit},
            auth=False,
            **opts,
        )

    def public_global_indices(
        self,
        *,
        keyword: Optional[str] = None,
        group: Optional[str] = None,
        listed: Optional[bool] = None,
        limit: Optional[int] = None,
        **opts: Any,
    ) -> Any:
        """全球指数公开清单 ``GET /public/v1/global-indices``。"""
        return self._get(
            '/public/v1/global-indices',
            {
                'keyword': keyword,
                'group': group,
                'listed': listed,
                'limit': limit,
            },
            auth=False,
            **opts,
        )

    def public_global_bonds(
        self,
        *,
        keyword: Optional[str] = None,
        group: Optional[str] = None,
        listed: Optional[bool] = None,
        limit: Optional[int] = None,
        **opts: Any,
    ) -> Any:
        """国际债券公开清单 ``GET /public/v1/global-bonds``。"""
        return self._get(
            '/public/v1/global-bonds',
            {
                'keyword': keyword,
                'group': group,
                'listed': listed,
                'limit': limit,
            },
            auth=False,
            **opts,
        )

    def public_usstocks(
        self,
        *,
        keyword: Optional[str] = None,
        market: Optional[str] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        **opts: Any,
    ) -> Any:
        """美股公开清单/搜索 ``GET /public/v1/usstocks``。``market`` 为 ``N``/``O``/``A``。"""
        return self._get(
            '/public/v1/usstocks',
            {
                'keyword': keyword,
                'market': market,
                'page': page,
                'limit': limit,
            },
            auth=False,
            **opts,
        )

    def corp_schema(self, **opts: Any) -> Any:
        return self._get('/public/v1/corp/schema', auth=False, **opts)

    def finance_schema(self, **opts: Any) -> Any:
        return self._get('/public/v1/finance/schema', auth=False, **opts)

    def etf_schema(self, **opts: Any) -> Any:
        return self._get('/public/v1/etf/schema', auth=False, **opts)

    def bond_schema(self, **opts: Any) -> Any:
        """债券字段说明 ``GET /public/v1/bond/schema``。"""
        return self._get('/public/v1/bond/schema', auth=False, **opts)

    def moneyflow_schema(self, **opts: Any) -> Any:
        return self._get('/public/v1/moneyflow/schema', auth=False, **opts)

    def moneyflow_ranking_catalog(self, **opts: Any) -> Any:
        """新浪资金流排名目录 ``GET /public/v1/moneyflow/ranking/catalog``。"""
        return self._get('/public/v1/moneyflow/ranking/catalog', auth=False, **opts)

    def moneyflow_ranking_live_catalog(self, **opts: Any) -> Any:
        """实时资金流排名目录 ``GET /public/v1/moneyflow/ranking/live/catalog``。"""
        return self._get('/public/v1/moneyflow/ranking/live/catalog', auth=False, **opts)

    def moneyflow_live_catalog(self, **opts: Any) -> Any:
        """实时个股资金流（按码）目录 ``GET /public/v1/moneyflow/live/catalog``。"""
        return self._get('/public/v1/moneyflow/live/catalog', auth=False, **opts)

    def plate_moneyflow_schema(self, **opts: Any) -> Any:
        """板块资金流字段说明 ``GET /public/v1/plate/moneyflow/schema``。"""
        return self._get('/public/v1/plate/moneyflow/schema', auth=False, **opts)

    def docs_md(self) -> str:
        return self.request_text('/public/v1/docs.md')

    def llms_txt(self) -> str:
        return self.request_text('/public/v1/llms.txt')

    def llms_full_txt(self) -> str:
        return self.request_text('/public/v1/llms-full.txt')
