"""LLM judge（真实模型）+ 人工抽检校准。"""
from __future__ import annotations

import json
import os
import random
from typing import Any


class LLMJudge:
    def __init__(self, model: str | None = None):
        from openai import OpenAI

        self.model = model or os.environ.get("JUDGE_MODEL", "deepseek-chat")
        self.client = OpenAI(
            api_key=os.environ["JUDGE_API_KEY"],
            base_url=os.environ.get("JUDGE_BASE_URL", "https://api.deepseek.com"),
        )

    def _ask_json(self, system: str, user: str) -> dict[str, Any]:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)

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
