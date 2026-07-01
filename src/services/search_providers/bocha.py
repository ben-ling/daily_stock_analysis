# -*- coding: utf-8 -*-
"""
博查搜索引擎实现

文档：https://bocha-ai.feishu.cn/wiki/RXEOw02rFiwzGSkd9mUcqoeAnNK
"""

import logging
from typing import List

import requests

from src.services.search_providers.base import (
    BaseSearchProvider,
    SearchResponse,
    SearchResult,
    post_with_retry,
)

logger = logging.getLogger(__name__)


class BochaSearchProvider(BaseSearchProvider):
    """
    博查搜索引擎

    特点：
    - 专为 AI 优化的中文搜索 API
    - 结果准确、摘要完整
    - 支持时间范围过滤和 AI 摘要
    """

    def __init__(self, api_keys: List[str]):
        super().__init__(api_keys, "Bocha")

    def _do_search(self, query: str, api_key: str, max_results: int, days: int = 7) -> SearchResponse:
        try:
            url = "https://api.bocha.cn/v1/web-search"

            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }

            freshness = "oneWeek"
            if days <= 1:
                freshness = "oneDay"
            elif days <= 7:
                freshness = "oneWeek"
            elif days <= 30:
                freshness = "oneMonth"
            else:
                freshness = "oneYear"

            payload = {
                "query": query,
                "freshness": freshness,
                "summary": True,
                "count": min(max_results, 50)
            }

            response = post_with_retry(url, headers=headers, json=payload, timeout=10)

            if response.status_code != 200:
                try:
                    if response.headers.get('content-type', '').startswith('application/json'):
                        error_data = response.json()
                        error_message = error_data.get('message', response.text)
                    else:
                        error_message = response.text
                except Exception:
                    error_message = response.text

                if response.status_code == 403:
                    error_msg = f"余额不足: {error_message}"
                elif response.status_code == 401:
                    error_msg = f"API KEY无效: {error_message}"
                elif response.status_code == 400:
                    error_msg = f"请求参数错误: {error_message}"
                elif response.status_code == 429:
                    error_msg = f"请求频率达到限制: {error_message}"
                else:
                    error_msg = f"HTTP {response.status_code}: {error_message}"

                logger.warning(f"[Bocha] 搜索失败: {error_msg}")
                return SearchResponse(
                    query=query, results=[], provider=self.name,
                    success=False, error_message=error_msg
                )

            try:
                data = response.json()
            except ValueError as e:
                error_msg = f"响应JSON解析失败: {str(e)}"
                logger.error(f"[Bocha] {error_msg}")
                return SearchResponse(
                    query=query, results=[], provider=self.name,
                    success=False, error_message=error_msg
                )

            if data.get('code') != 200:
                error_msg = data.get('msg') or f"API返回错误码: {data.get('code')}"
                return SearchResponse(
                    query=query, results=[], provider=self.name,
                    success=False, error_message=error_msg
                )

            logger.info(f"[Bocha] 搜索完成，query='{query}'")
            logger.debug(f"[Bocha] 原始响应: {data}")

            results = []
            web_pages = data.get('data', {}).get('webPages', {})
            value_list = web_pages.get('value', [])

            for item in value_list[:max_results]:
                snippet = item.get('summary') or item.get('snippet', '')
                if snippet:
                    snippet = snippet[:500]

                results.append(SearchResult(
                    title=item.get('name', ''),
                    snippet=snippet,
                    url=item.get('url', ''),
                    source=item.get('siteName') or self._extract_domain(item.get('url', '')),
                    published_date=item.get('datePublished'),
                ))

            logger.info(f"[Bocha] 成功解析 {len(results)} 条结果")

            return SearchResponse(
                query=query, results=results, provider=self.name, success=True,
            )

        except requests.exceptions.Timeout:
            error_msg = "请求超时"
            logger.error(f"[Bocha] {error_msg}")
            return SearchResponse(
                query=query, results=[], provider=self.name,
                success=False, error_message=error_msg
            )
        except requests.exceptions.RequestException as e:
            error_msg = f"网络请求失败: {str(e)}"
            logger.error(f"[Bocha] {error_msg}")
            return SearchResponse(
                query=query, results=[], provider=self.name,
                success=False, error_message=error_msg
            )
        except Exception as e:
            error_msg = f"未知错误: {str(e)}"
            logger.error(f"[Bocha] {error_msg}")
            return SearchResponse(
                query=query, results=[], provider=self.name,
                success=False, error_message=error_msg
            )

    @staticmethod
    def _extract_domain(url: str) -> str:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc.replace('www.', '')
            return domain or '未知来源'
        except Exception:
            return '未知来源'