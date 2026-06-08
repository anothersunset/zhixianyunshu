"""LLM judge（真实模型）+ 人工抽检校准。

支持两种模式：
1. 直连 DeepSeek API（默认）
2. 通过后端 /api/judge 代理（设置 JUDGE_BACKEND_URL），复用后端的 RestClient 连接池，避免
   中国大陆环境下 Python 直连 API 容易挂起的问题。
"""
from __future__ import annotations

import json
import os
import random
import time
from typing import Any

import requests


class LLMJudge:
    def __init__(self, model: str | None = None, backend_url: str | None = None):
        self.model = model or os.environ.get("JUDGE_MODEL", "deepseek-v4-pro")
        self.backend_url = (
            backend_url
            or os.environ.get("JUDGE_BACKEND_URL", "")
            or os.environ.get("ZHIQIAN_MIGRATE_URL", "")
        ).rstrip("/")

        if self.backend_url:
            # 通过后端代理——复用后端稳定的 RestClient
            self._ask_json = self._ask_via_backend
        else:
            # 直连 DeepSeek API
            from openai import OpenAI

            self.thinking_enabled = os.environ.get("JUDGE_THINKING_ENABLED", "false").lower() in {"1", "true", "yes"}
            self.reasoning_effort = os.environ.get("JUDGE_REASONING_EFFORT", "medium")
            self.client = OpenAI(
                api_key=os.environ["JUDGE_API_KEY"],
                base_url=os.environ.get("JUDGE_BASE_URL", "https://api.deepseek.com/v1"),
                timeout=30.0,
                max_retries=1,
            )
            self._ask_json = self._ask_direct

    def _ask_direct(self, system: str, user: str) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }
        if self.model.lower().startswith("deepseek-v4") and self.thinking_enabled:
            params["reasoning_effort"] = self.reasoning_effort
            params["extra_body"] = {"thinking": {"type": "enabled"}}
        else:
            params["temperature"] = 0

        max_retries = 3
        base_backoff = 2.0
        last_exc = None
        for attempt in range(max_retries + 1):
            try:
                resp = self.client.chat.completions.create(**params)
                return json.loads(resp.choices[0].message.content)
            except Exception as exc:
                last_exc = exc
                if attempt < max_retries:
                    wait = base_backoff * (2 ** attempt)
                    print(f"[judge] API 调用失败 (attempt={attempt+1}/{max_retries+1}), {wait:.0f}s 后重试: {exc}")
                    time.sleep(wait)
        raise RuntimeError(f"judge API 调用最终失败: {last_exc}")

    def _ask_via_backend(self, _system: str, user: str) -> dict[str, Any]:
        """通过后端 /api/judge 代理调用——使用与后端 Agent 相同的 RestClient。"""
        # 从 user 消息中提取参数（与后端 judge 端点的格式对齐）
        user_data = json.loads(user.split("\n输出")[0]) if "\n输出" in user else json.loads(user)
        if "pred" in user_data and "gold" in user_data:
            # sql_equal 类型
            target = ""  # 从 system 消息提取 target dialect
            import re
            m = re.search(r"在\s*(\S+)\s*上", _system)
            if m:
                target = m.group(1)
            body = {"type": "sql_equal", "pred": user_data["pred"], "gold": user_data["gold"], "target": target}
        else:
            # point_covered 类型
            body = {"type": "point_covered", "gold_point": user_data["gold_point"],
                    "pred_points": user_data["pred_points"]}

        max_retries = 3
        base_backoff = 2.0
        last_exc = None
        for attempt in range(max_retries + 1):
            try:
                resp = requests.post(
                    self.backend_url + "/api/judge",
                    json=body,
                    timeout=120,
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:
                last_exc = exc
                if attempt < max_retries:
                    wait = base_backoff * (2 ** attempt)
                    print(f"[judge:backend] 调用失败 (attempt={attempt+1}/{max_retries+1}), {wait:.0f}s 后重试: {exc}")
                    time.sleep(wait)
        raise RuntimeError(f"judge backend 调用最终失败: {last_exc}")

    def sql_semantically_equal(self, pred: str, gold: str, target: str) -> bool:
        sys = "你是资深数据库迁移评审。判断两段目标 SQL 在 " + target + " 上是否语义等价，只输出 JSON。"
        usr = json.dumps({"pred": pred, "gold": gold}, ensure_ascii=False)
        usr += '\n输出 {"equal": true/false, "reason": "..."}'
        return bool(self._ask_json(sys, usr).get("equal"))

    def point_covered(self, gold_point: str, pred_points: list[str]) -> bool:
        sys = "判断【标准要点】是否被【模型报告要点】覆盖，只输出 JSON。"
        usr = json.dumps({"gold_point": gold_point, "pred_points": pred_points}, ensure_ascii=False)
        usr += '\n输出 {"covered": true/false}'
        return bool(self._ask_json(sys, usr).get("covered"))


def cohen_kappa(judge_labels: list[int], human_labels: list[int]) -> float:
    """LLM judge 与人工标注的一致性。"""
    assert len(judge_labels) == len(human_labels) and judge_labels
    n = len(judge_labels)
    po = sum(1 for a, b in zip(judge_labels, human_labels) if a == b) / n
    labels = set(judge_labels) | set(human_labels)
    pe = sum((judge_labels.count(l) / n) * (human_labels.count(l) / n) for l in labels)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def sample_for_human_review(rows: list[dict], ratio: float = 0.2, seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    k = max(1, int(len(rows) * ratio))
    return rng.sample(rows, k)
