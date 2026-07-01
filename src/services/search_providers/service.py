# -*- coding: utf-8 -*-
"""
搜索服务 - Service 聚合层

提供 SearchService / get_search_service / reset_search_service 的统一入口。
当前从 src.search_service reexport，保持新包可导入且不破坏现有外部引用与测试。
后续可逐步将 SearchService 实现迁入本包。
"""

from src.search_service import (
    SearchService,
    get_search_service,
    reset_search_service,
)

__all__ = [
    "SearchService",
    "get_search_service",
    "reset_search_service",
]
