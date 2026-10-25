"""KlineShare Python SDK."""

from __future__ import annotations

from klineshare.async_client import AsyncClient, async_pro_api
from klineshare.client import Client, pro_api, set_api_key, get_api_key
from klineshare.errors import (
    KlineShareAuthError,
    KlineShareError,
    KlineShareQuotaError,
    KlineShareRateLimitError,
)
from klineshare.level2 import LEVEL2_CHANNELS, Level2LiveFeed
from klineshare.symbols import (
    normalize_hk_symbol,
    normalize_hk_symbols,
    normalize_symbol,
    normalize_symbols,
)
from klineshare.ws import WebSocketFeed

__all__ = [
    'Client',
    'AsyncClient',
    'pro_api',
    'async_pro_api',
    'set_api_key',
    'get_api_key',
    'normalize_symbol',
    'normalize_symbols',
    'normalize_hk_symbol',
    'normalize_hk_symbols',
    'WebSocketFeed',
    'Level2LiveFeed',
    'LEVEL2_CHANNELS',
    'KlineShareError',
    'KlineShareAuthError',
    'KlineShareRateLimitError',
    'KlineShareQuotaError',
]

__version__ = '0.2.7'
