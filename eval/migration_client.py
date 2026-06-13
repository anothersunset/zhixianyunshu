"""适配层：把评测框架接到真实 6 节点 AgentGraph。

默认通过 HTTP 调用外部/本机迁移服务：
SchemaAnalyzer -> ContextRetriever -> SqlReasoner -> SqlPatcher -> SqlCritic -> ReportSummarizer

retrieval 参数用于消融：
  'bm25' | 'vector' | 'vector_rerank' | 'crag' | 'full'
服务端应据此只切换 ContextRetriever 检索配置，其余链路保持固定。
"""
from __future__ import annotations

import os
import time
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
    # 类级别：上次请求完成时间，用于跨实例节流
    _last_request_end: float = 0.0
    _consecutive_errors: int = 0

    def __init__(self, base_url: str | None = None, cooldown: float | None = None):
        # 分段拼接，避免把插值直接写进字符串模板。
        self.base_url = (
            base_url
            or os.environ.get("ZHIQIAN_MIGRATE_URL")
            or os.environ.get("ZHIQIAN_RAG_URL")
            or "http://localhost:8080"
        )
        self.timeout_seconds = float(os.environ.get("ZHIQIAN_MIGRATE_TIMEOUT", "120"))
        self.allow_mock = os.environ.get("ZHIQIAN_ALLOW_MOCK_EVAL", "").lower() in {"1", "true", "yes"}
        # 冷却时间（秒）：两次请求之间的最小间隔，防止后端过载
        self.cooldown = cooldown if cooldown is not None else float(os.environ.get("ZHIQIAN_MIGRATE_COOLDOWN", "3"))
        # 复用 TCP 连接（HTTP keep-alive）
        self.session = requests.Session()

    def _throttle(self):
        """请求间冷却：确保两次请求间隔 >= cooldown 秒，连续失败时自适应增大。"""
        import time as _time
        effective_cooldown = min(self.cooldown * (1.5 ** min(MigrationClient._consecutive_errors, 4)), 60)
        elapsed = _time.time() - MigrationClient._last_request_end
        if elapsed < effective_cooldown:
            wait = effective_cooldown - elapsed
            print(f"[throttle] 冷却 {wait:.1f}s (连续失败={MigrationClient._consecutive_errors})", flush=True)
            _time.sleep(wait)

    def batch_throttle(self):
        """批次冷却：case 间调用，确保两个 case 批次间有足够间隔。"""
        import time as _time
        effective_cooldown = min(self.cooldown * (1.5 ** min(MigrationClient._consecutive_errors, 4)), 60)
        elapsed = _time.time() - MigrationClient._last_request_end
        if elapsed < effective_cooldown:
            wait = effective_cooldown - elapsed
            print(f"[batch-throttle] case 间冷却 {wait:.1f}s", flush=True)
            _time.sleep(wait)

    def run_migration(self, *, source_sql: str, pair: str, retrieval: str, fast: bool = False, skip_throttle: bool = False) -> MigrationResult:
        endpoint = self.base_url.rstrip("/") + "/migrate"
        payload = {"source_sql": source_sql, "pair": pair, "retrieval": retrieval, "fast": fast}

        if not skip_throttle:
            self._throttle()

        print(f"  [migrate] -> {pair} retrieval={retrieval} fast={fast} ...", end="", flush=True)
        max_retries = 3
        base_backoff = 2.0
        last_exc = None
        for attempt in range(max_retries + 1):
            try:
                resp = self.session.post(endpoint, json=payload, timeout=self.timeout_seconds)
                resp.raise_for_status()
                data = resp.json()
                MigrationClient._last_request_end = time.time()
                MigrationClient._consecutive_errors = 0  # 成功则重置
                print(f" OK ({resp.elapsed.total_seconds():.1f}s)", flush=True)
                break
            except Exception as exc:
                last_exc = exc
                MigrationClient._consecutive_errors += 1
                print(f" FAIL ({exc})", flush=True)
                if attempt < max_retries:
                    wait = base_backoff * (2 ** attempt)
                    print(f"  [migrate] retry {attempt+1}/{max_retries+1}, wait {wait:.0f}s", flush=True)
                    time.sleep(wait)
        else:
            MigrationClient._last_request_end = time.time()
            raise RuntimeError(f"migration 调用最终失败: {last_exc}")

        if data.get("raw", {}).get("real") is False and not self.allow_mock:
            raise RuntimeError(
                "Migration service is running with mock LLM output. "
                "Set LLM_API_KEY in zhiqian/deploy/.env and restart backend before real eval. "
                "For smoke tests only, set ZHIQIAN_ALLOW_MOCK_EVAL=1."
            )
        return MigrationResult(
            target_sql=data.get("target_sql", ""),
            report_points=data.get("report_points", []),
            risk_level=data.get("risk_level"),
            confidence=data.get("confidence"),
            retrieved_ids=data.get("retrieved_ids", []),
            raw=data,
        )
