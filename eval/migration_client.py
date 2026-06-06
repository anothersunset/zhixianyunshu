"""
适配层：把评测框架接到真实 6 节点 AgentGraph。

默认通过 HTTP 调用外部/本机迁移服务：
SchemaAnalyzer -> ContextRetriever -> SqlReasoner -> SqlPatcher -> SqlCritic -> ReportSummarizer

retrieval 参数用于消融：
  'bm25' | 'vector' | 'vector_rerank' | 'crag' | 'full'
服务端应据此只切换 ContextRetriever 检索配置，其余链路保持固定。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import requests


@dataclass
class MigrationResult:
    target_sql: str
    report_points: list[str]
    risk_level: str | None = None
    confidence: float | None = None  # 仅记录，绝不作为指标
    retrieved_ids: list[str] = field(default_factory=list)  # 用于 Recall@k
    raw: dict[str, Any] = field(default_factory=dict)


class MigrationClient:
    def __init__(self, base_url: str | None = None):
        # 分段拼接，避免把插值直接写进字符串模板。
        self.base_url = (
            base_url
            or os.environ.get("ZHIQIAN_MIGRATE_URL")
            or os.environ.get("ZHIQIAN_RAG_URL")
            or "http://localhost:8080"
        )

    def run_migration(self, *, source_sql: str, pair: str, retrieval: str) -> MigrationResult:
        endpoint = self.base_url.rstrip("/") + "/migrate"
        payload = {"source_sql": source_sql, "pair": pair, "retrieval": retrieval}
        resp = requests.post(endpoint, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return MigrationResult(
            target_sql=data.get("target_sql", ""),
            report_points=data.get("report_points", []),
            risk_level=data.get("risk_level"),
            confidence=data.get("confidence"),
            retrieved_ids=data.get("retrieved_ids", []),
            raw=data,
        )
