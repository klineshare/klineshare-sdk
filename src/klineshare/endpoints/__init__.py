"""Endpoint mixins for Client."""

from klineshare.endpoints.catalog_bond import CatalogBondEndpoints
from klineshare.endpoints.extended import ExtendedEndpoints
from klineshare.endpoints.index_etf import IndexEtfEndpoints
from klineshare.endpoints.market import MarketEndpoints
from klineshare.endpoints.meta import MetaEndpoints
from klineshare.endpoints.topics import TopicsEndpoints
from klineshare.endpoints.ws_endpoints import WsEndpoints

__all__ = [
    'CatalogBondEndpoints',
    'ExtendedEndpoints',
    'IndexEtfEndpoints',
    'MarketEndpoints',
    'MetaEndpoints',
    'TopicsEndpoints',
    'WsEndpoints',
]
