"""WebSocket / Level2 endpoint methods for Client."""

from __future__ import annotations

from typing import Any, Iterable, List, Optional, Sequence, Union

from klineshare.errors import KlineShareAuthError, KlineShareQuotaError
from klineshare.level2 import Level2LiveFeed, _as_channel_list, _as_symbol_list as _l2_syms
from klineshare.ws import WebSocketFeed, _as_symbol_list, build_ws_url


class WsEndpoints:
    """Mixin: Tick/futures WebSocket + Level2."""

    def _sync_api_base_for_stream(self) -> None:
        """Best-effort refresh so long-lived connects prefer current ``api_base``."""
        if not getattr(self, 'follow_api_base', True) or not self.api_key:
            return
        try:
            self._ensure_limits()
        except Exception:
            pass

    def _ws_feed(
        self,
        path: str,
        *,
        query: Optional[dict] = None,
        timeout: Optional[float] = None,
    ) -> WebSocketFeed:
        if not self.api_key:
            raise KlineShareAuthError(
                '未配置 API Key：请 ks.set_api_key(...) 或设置环境变量 KLINESHARE_API_KEY',
                code=401,
                http_status=401,
            )
        self._sync_api_base_for_stream()
        url = build_ws_url(self.base_url, path, api_key=self.api_key, query=query)

        def _on_wrong_entry(hinted: str, _msg: dict) -> Optional[str]:
            if not self._adopt_api_base(hinted):
                return None
            return build_ws_url(self.base_url, path, api_key=self.api_key, query=query)

        return WebSocketFeed(
            url,
            api_key=self.api_key,
            timeout=timeout if timeout is not None else self.timeout,
            on_wrong_entry=_on_wrong_entry if getattr(self, 'follow_api_base', True) else None,
        )

    def _ensure_stream_symbol_quota(self, symbol: Any, *, limit_attr: str, label: str) -> List[str]:
        syms = _as_symbol_list(symbol)
        if self.limits_mode == 'off':
            return syms
        try:
            snap = self._ensure_limits()
        except Exception:
            return syms
        limit = getattr(snap, limit_attr, None)
        if limit is None and isinstance(snap.raw, dict):
            try:
                limit = int(snap.raw[limit_attr]) if snap.raw.get(limit_attr) is not None else None
            except (TypeError, ValueError, KeyError):
                limit = None
        if limit is not None and len(syms) > int(limit):
            raise KlineShareQuotaError(
                f'{label} 订阅标的数超过上限 {limit}',
                limit_name=limit_attr,
                limit_value=limit,
                got=len(syms),
                code=400,
            )
        return syms

    def realtime_ws(
        self,
        symbol: Optional[Union[str, Iterable[str]]] = None,
        *,
        ks_code: Optional[Union[str, Iterable[str]]] = None,
        timeout: Optional[float] = None,
    ) -> WebSocketFeed:
        """
        沪深京个股 Tick WebSocket ``/v1/realtime/ws``。

        返回可 ``with`` / 迭代的 ``WebSocketFeed``；可用 ``feed.sub`` / ``feed.unsub``。
        需要：``pip install "klineshare[ws]"``。
        """
        raw = symbol if symbol is not None else ks_code
        syms = self._ensure_stream_symbol_quota(
            raw, limit_attr='max_realtime_stream_symbols', label='Tick WS',
        )
        query = {}
        if syms:
            query['symbol'] = ','.join(syms)
        return self._ws_feed('/v1/realtime/ws', query=query, timeout=timeout)

    def level2(
        self,
        symbol: Optional[Union[str, Iterable[str]]] = None,
        *,
        ks_code: Optional[Union[str, Iterable[str]]] = None,
        channels: Optional[Union[str, Sequence[str]]] = None,
        binary: Optional[str] = None,
        bind: Optional[str] = None,
        dump: str = 'none',
        run_for: Optional[float] = None,
        download: bool = True,
    ) -> Level2LiveFeed:
        """
        Level2 行情订阅。

        ``channels``: ``depth``（十档）/ ``orders``（委托队列）/ ``trades``（逐笔成交）/
        ``entrust``（逐笔委托）；可多选。须在 ``GET /v1/me`` 的 ``level2_channels``
        （当下可订）内；未列出的通道会跳过。默认四个通道都订。

        用法::

            with pro.level2(symbol="600519.SS", channels="depth,trades") as feed:
                for msg in feed:
                    ...
        """
        if not self.api_key:
            raise KlineShareAuthError(
                '未配置 API Key：请 ks.set_api_key(...) 或设置环境变量 KLINESHARE_API_KEY',
                code=401,
                http_status=401,
            )
        raw = symbol if symbol is not None else ks_code
        syms = _l2_syms(raw)
        ch_list = _as_channel_list(channels)

        # Prefer current api_base before spawning ks-live (L2_API_BASE is fixed at start).
        self._sync_api_base_for_stream()

        if self.limits_mode != 'off':
            try:
                snap = self._ensure_limits()
                raw_me = snap.raw if isinstance(snap.raw, dict) else {}
                slots = raw_me.get('max_level2_slots')
                allowed = raw_me.get('level2_channels')
                if allowed and ch_list:
                    allow = set(allowed)
                    keep = [c for c in ch_list if c in allow]
                    skipped = [c for c in ch_list if c not in allow]
                    if skipped and not keep:
                        raise KlineShareQuotaError(
                            f'当前不支持 Level2 通道: {skipped}',
                            limit_name='level2_channels',
                            limit_value=allowed,
                            got=skipped,
                            code=403,
                        )
                    ch_list = keep or ch_list
                n_ch = max(1, len(ch_list) or 1)
                used = len(syms) * n_ch
                if slots is not None and used > int(slots):
                    raise KlineShareQuotaError(
                        f'Level2 订阅槽（标的×通道）超过上限 {slots}',
                        limit_name='max_level2_slots',
                        limit_value=slots,
                        got=used,
                        code=400,
                    )
            except KlineShareQuotaError:
                raise
            except Exception:
                pass

        return Level2LiveFeed(
            api_key=self.api_key,
            base_url=self.base_url,
            symbols=syms,
            channels=ch_list,
            binary=binary,
            bind=bind,
            dump=dump,
            run_for=run_for,
            download=download,
        )

    def futures_ws(
        self,
        symbol: Optional[Union[str, Iterable[str]]] = None,
        *,
        exchange: Optional[str] = None,
        timeout: Optional[float] = None,
        **query: Any,
    ) -> WebSocketFeed:
        """国内期货 WebSocket ``/v1/futures/ws``。"""
        q = dict(query)
        if exchange:
            q['exchange'] = exchange
        syms = self._ensure_stream_symbol_quota(
            symbol, limit_attr='max_futures_stream_symbols', label='Futures WS',
        )
        if syms:
            q['symbol'] = ','.join(syms)
        return self._ws_feed('/v1/futures/ws', query=q, timeout=timeout)

    def futures_v2_ws(
        self,
        symbol: Optional[Union[str, Iterable[str]]] = None,
        *,
        exchange: Optional[str] = None,
        timeout: Optional[float] = None,
        **query: Any,
    ) -> WebSocketFeed:
        """国内期货 V2 WebSocket ``/v1/futures-v2/ws``。"""
        q = dict(query)
        if exchange:
            q['exchange'] = exchange
        limit_attr = 'max_futures_v2_stream_symbols'
        if self.limits_mode != 'off':
            try:
                snap = self._ensure_limits()
                raw_me = snap.raw if isinstance(snap.raw, dict) else {}
                if raw_me.get('max_futures_v2_stream_symbols') is None:
                    limit_attr = 'max_futures_stream_symbols'
            except Exception:
                limit_attr = 'max_futures_stream_symbols'
        syms = self._ensure_stream_symbol_quota(
            symbol, limit_attr=limit_attr, label='Futures V2 WS',
        )
        if syms:
            q['symbol'] = ','.join(syms)
        return self._ws_feed('/v1/futures-v2/ws', query=q, timeout=timeout)

    # URL helpers (no websocket-client required)
    def realtime_ws_url(
        self,
        symbol: Optional[Union[str, Iterable[str]]] = None,
        *,
        ks_code: Optional[Union[str, Iterable[str]]] = None,
    ) -> str:
        raw = symbol if symbol is not None else ks_code
        syms = _as_symbol_list(raw)
        q = {'api_key': self.api_key}
        if syms:
            q['symbol'] = ','.join(syms)
        return build_ws_url(self.base_url, '/v1/realtime/ws', query=q)

    def futures_ws_url(self, **query: Any) -> str:
        q = {'api_key': self.api_key, **query}
        return build_ws_url(self.base_url, '/v1/futures/ws', query=q)

    def futures_v2_ws_url(self, **query: Any) -> str:
        q = {'api_key': self.api_key, **query}
        return build_ws_url(self.base_url, '/v1/futures-v2/ws', query=q)
