"""
v2-step-12: CRAG web_search 补充检索。

优先顺序:
1. SearXNG (设 RAG_SEARXNG_URL 则优先走自部署)
2. duckduckgo-search (零 key, 装包即可)
3. 都不可用 → 返回空列表 (CRAG 降级为仅本地)

设计只返回轻量摄要以避免胆拍 LLM token。
"""
from __future__ import annotations

import logging
import os
from typing import List, Dict, Any

log = logging.getLogger("crag.web_search")


def _try_searxng(query: str, top_k: int) -> List[Dict[str, Any]]:
    url = os.environ.get("RAG_SEARXNG_URL", "").strip()
    if not url:
        return []
    try:
        import httpx
        with httpx.Client(timeout=8.0) as c:
            r = c.get(
                f"{url.rstrip('/')}/search",
                params={"q": query, "format": "json", "language": "zh-CN"},
            )
            r.raise_for_status()
            data = r.json()
        results = []
        for item in (data.get("results") or [])[:top_k]:
            results.append({
                "id": f"web-searxng-{item.get('url', '')[:60]}",
                "text": (item.get("content") or item.get("title") or "")[:1500],
                "score": 1.0,
                "source": "web:searxng",
                "meta": {"title": item.get("title"), "url": item.get("url")},
            })
        return results
    except Exception as e:
        log.warning("[crag] SearXNG 查询失败 %r", e)
        return []


def _try_duckduckgo(query: str, top_k: int) -> List[Dict[str, Any]]:
    try:
        from duckduckgo_search import DDGS  # type: ignore
    except ImportError:
        log.info("[crag] duckduckgo-search 未安装, 跳过")
        return []
    try:
        results = []
        with DDGS(timeout=8) as ddgs:
            for i, hit in enumerate(ddgs.text(query, region="cn-zh", max_results=top_k)):
                results.append({
                    "id": f"web-ddg-{i}",
                    "text": (hit.get("body") or hit.get("title") or "")[:1500],
                    "score": 1.0 - i * 0.05,
                    "source": "web:duckduckgo",
                    "meta": {"title": hit.get("title"), "url": hit.get("href")},
                })
        return results
    except Exception as e:
        log.warning("[crag] DuckDuckGo 查询失败 %r", e)
        return []


class WebSearcher:
    """统一 web 检索入口。失败不抛, 返 []。"""

    def __init__(self, top_k: int = 5):
        self.top_k = top_k

    def search(self, query: str) -> List[Dict[str, Any]]:
        # 1. SearXNG 优先
        results = _try_searxng(query, self.top_k)
        if results:
            return results
        # 2. 降级 duckduckgo
        results = _try_duckduckgo(query, self.top_k)
        return results or []
