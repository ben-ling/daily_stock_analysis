# -*- coding: utf-8 -*-
"""
搜索服务 - 提供商模块聚合

集中导出所有搜索提供商与基础类型，保持向后兼容。
"""

from src.services.search_providers.base import (
    BaseSearchProvider,
    SearchResponse,
    SearchResult,
    _extract_domain,
    fetch_url_content,
    get_with_retry,
    post_with_retry,
)

from src.services.search_providers.tavily import TavilySearchProvider
from src.services.search_providers.serpapi import SerpAPISearchProvider
from src.services.search_providers.bocha import BochaSearchProvider
from src.services.search_providers.anspire import AnspireSearchProvider
from src.services.search_providers.minimax import MiniMaxSearchProvider
from src.services.search_providers.brave import BraveSearchProvider
from src.services.search_providers.searxng import SearXNGSearchProvider
from src.services.search_providers.service import (
    SearchService,
    get_search_service,
    reset_search_service,
)

__all__ = [
    "BaseSearchProvider",
    "SearchResponse",
    "SearchResult",
    "TavilySearchProvider",
    "SerpAPISearchProvider",
    "BochaSearchProvider",
    "AnspireSearchProvider",
    "MiniMaxSearchProvider",
    "BraveSearchProvider",
    "SearXNGSearchProvider",
    "SearchService",
    "get_search_service",
    "reset_search_service",
    "fetch_url_content",
    "get_with_retry",
    "post_with_retry",
    "_extract_domain",
]