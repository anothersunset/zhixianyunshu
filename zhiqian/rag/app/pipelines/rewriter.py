from __future__ import annotations

import re
from typing import Optional


class QueryRewriter:
    """
    查询重写器。默认实现仅做轻量规范化 + 所在领域名词补充，不依赖 LLM。
    接入真实 LLM 后可替换为提示词驱动的重写。
    """

    _DOMAIN_HINTS = [
        (re.compile(r"mysql", re.I), "MySQL"),
        (re.compile(r"opengauss", re.I), "openGauss"),
        (re.compile(r"(迁移|迁转|改造)"), "数据库迁移"),
    ]

    def rewrite(self, question: str, llm: Optional[object] = None) -> str:
        q = (question or "").strip()
        if not q:
            return q
        # 去除多余空白
        q = re.sub(r"\s+", " ", q)
        hints = [tag for pattern, tag in self._DOMAIN_HINTS if pattern.search(q) and tag not in q]
        if hints:
            q = q + " " + " ".join(hints)
        return q
