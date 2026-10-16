"""Optional async facade over the sync Client (stdlib asyncio only)."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from klineshare.client import Client, DEFAULT_LIMITS_TTL, pro_api
from klineshare.limits.quota import DEFAULT_KLINE_HEAVY_THRESHOLD


class AsyncClient:
    """
    Thin async wrapper: each call runs the sync ``Client`` in a worker thread.

    Does not add httpx/aiohttp. Suitable for asyncio apps that need non-blocking
    wait around the existing sync Session + limits pipeline.
    """

    def __init__(self, client: Optional[Client] = None, **kwargs: Any) -> None:
        self._client = client or pro_api(**kwargs)

    @property
    def sync(self) -> Client:
        return self._client

    async def request(self, *args: Any, **kwargs: Any) -> Any:
        return await asyncio.to_thread(self._client.request, *args, **kwargs)

    async def get(self, *args: Any, **kwargs: Any) -> Any:
        return await asyncio.to_thread(self._client.get, *args, **kwargs)

    async def kline(self, *args: Any, **kwargs: Any) -> Any:
        return await asyncio.to_thread(self._client.kline, *args, **kwargs)

    async def realtime(self, *args: Any, **kwargs: Any) -> Any:
        return await asyncio.to_thread(self._client.realtime, *args, **kwargs)

    async def me(self, *args: Any, **kwargs: Any) -> Any:
        return await asyncio.to_thread(self._client.me, *args, **kwargs)

    async def health(self, *args: Any, **kwargs: Any) -> Any:
        return await asyncio.to_thread(self._client.health, *args, **kwargs)

    async def refresh_limits(self) -> Any:
        return await asyncio.to_thread(self._client.refresh_limits)

    async def aclose(self) -> None:
        await asyncio.to_thread(self._client.close)

    async def __aenter__(self) -> 'AsyncClient':
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()


def async_pro_api(
    api_key: Optional[str] = None,
    **kwargs: Any,
) -> AsyncClient:
    """Factory mirroring ``pro_api`` but returning ``AsyncClient``."""
    kwargs.setdefault('limits_ttl', DEFAULT_LIMITS_TTL)
    kwargs.setdefault('kline_heavy_threshold', DEFAULT_KLINE_HEAVY_THRESHOLD)
    return AsyncClient(pro_api(api_key=api_key, **kwargs))
