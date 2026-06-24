"""Phase 3 Step 3.2: KB 补充生成器。

读取 failure_analysis.json → 对 critical/severe 失败聚类，用 LLM 生成目标 KB 文档 →
写入 kb/pending/ (待人工审核)。

安全闸门：仅写入 kb/pending/，绝不自动写入 kb/active/。

用法:
    python -m eval.kb_generator \
        --analysis eval/results/failure_analysis.json \
        --out kb/pending

或指定严重性阈值:
    python -m eval.kb_generator \
        --analysis eval/results/failure_analysis.json \
        --min-fail-rate 0.5 \
        --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

# ── KB 目录 ──
PROJECT_ROOT = Path(__file__).resolve().parent.parent
KB_PENDING = PROJECT_ROOT / "kb" / "pending"

# ── LLM 调用 ──

def _llm_chat(prompt: str, system: str = "You are a senior database migration expert.") -> str:
    """调用 LLM（复用项目已有的 LLM API 配置）。"""
    api_key = os.environ.get("LLM_API_KEY", "")
    base_url = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/v1")
    model = os.environ.get("LLM_CHAT_MODEL", "deepseek-chat")

    if not api_key:
        raise RuntimeError("LLM_API_KEY not set in environment. Cannot generate KB docs without LLM.")

    resp = requests.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.0,
            "max_tokens": 2048,
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


# ── KB 文档生成 ──

def generate_kb_doc(cluster: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """为单个失败聚类生成 KB 文档。返回 YAML-ready dict 或 None。"""
    keyword = cluster["keyword"]
    mapping = cluster["mapping"]
    category = cluster["category"]
    fail_rate = cluster["fail_rate"]
    samples = cluster.get("sample_cases", [])[:3]  # 最多 3 个样本

    # 构建样本展示
    sample_text = ""
    for i, s in enumerate(samples, 1):
        sample_text += f"""
Sample {i}:
  Source SQL: {s.get('source_sql', 'N/A')}
  Expected (gold): {s.get('gold_sql', 'N/A')}
  Actual (pred): {s.get('pred_sql', 'N/A')}
  Error: {s.get('error', 'none')}
"""

    prompt = f"""You are a senior database migration expert. Generate a KB documentation entry for a recurring
SQL dialect conversion failure pattern.

PATTERN: {keyword} → {mapping}
FAILURE RATE: {fail_rate:.0%}
CATEGORY: {category}

FAILED EXAMPLES:
{sample_text}

TASK: Write a concise KB document (200-400 words) that explains:
1. What the source construct does
2. The correct target equivalent
3. Common pitfalls that cause conversion failure
4. A correct source→target example

Output in YAML format (copy exactly):
```yaml
category: {category.upper()}
docs:
  - id: kb-generated-{_slugify(keyword)}
    source_dialect: {_infer_dialect(keyword)}
    target_dialect: postgresql
    text: |
      <your multi-line documentation here>
    source: kb/auto/{_slugify(keyword)}
    terms: ["{keyword.replace('(','').replace(')','').lower()}", "conversion", "migration"]
```

Generate ONLY the YAML block, no other text."""

    try:
        reply = _llm_chat(prompt)
        # 提取 YAML 块
        yaml_text = _extract_yaml(reply)
        if yaml_text:
            import yaml as _yaml
            return _yaml.safe_load(yaml_text)
    except Exception as e:
        print(f"  [ERROR] Failed to generate KB doc for {keyword}: {e}")
    return None


def _slugify(keyword: str) -> str:
    """将关键词转换为文件安全的 slug。"""
    return keyword.lower().replace("(", "-").replace(")", "").replace(" ", "-").replace("_", "-")


def _infer_dialect(keyword: str) -> str:
    """根据关键词推断源方言。"""
    kw = keyword.lower()
    if kw in ("rownum", "connect by", "start with", "merge into", "months_between(",
              "decode(", "nvl(", "sysdate", "from dual", "(+)", "pivot(", "unpivot(",
              "listagg(", "regexp_substr(", "add_months(", "to_char(", "to_date(",
              "instr(", "initcap(", "user", "uid", "to_number(", "substr(",
              "systimestamp", "to_timestamp(", "regexp_replace(", "regexp_like(",
              "timestamp_trunc("):
        return "oracle"
    if kw in ("ifnull(", "date_format(", "group_concat(", "auto_increment", "enum(",
              "on duplicate key", "regexp", "now()", "tinyint", "bit(",
              "engine=", "character set", "collate", "unsigned", "zerofill", "`"):
        return "mysql"
    return "unknown"


def _extract_yaml(text: str) -> str:
    """从 LLM 回复中提取 YAML 块。"""
    # 尝试提取 ```yaml ... ``` 块
    import re
    m = re.search(r'```(?:yaml)?\s*\n?(.*?)```', text, re.DOTALL)
    if m:
        return m.group(1).strip()
    # 如果没有代码块，尝试找 category: 开头的内容
    m = re.search(r'(category:.*)', text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text.strip()


# ── 批量生成 ──

def generate_all(
    clusters: List[Dict[str, Any]],
    min_fail_rate: float = 0.5,
    dry_run: bool = False,
) -> List[Dict[str, Any]]:
    """为所有符合条件的聚类生成 KB 文档。"""
    generated = []
    eligible = [c for c in clusters if c["fail_rate"] >= min_fail_rate]

    print(f"[kb_generator] {len(eligible)}/{len(clusters)} clusters eligible (fail_rate >= {min_fail_rate:.0%})")
    if dry_run:
        print("[kb_generator] DRY RUN — 不会写入文件")
        for c in eligible:
            print(f"  Would generate: {c['keyword']} (fail_rate={c['fail_rate']:.0%})")
        return []

    for i, cluster in enumerate(eligible, 1):
        keyword = cluster["keyword"]
        print(f"\n[{i}/{len(eligible)}] Generating KB doc for: {keyword}")
        print(f"  fail_rate={cluster['fail_rate']:.0%}, modes={cluster.get('failing_modes', [])}")

        doc = generate_kb_doc(cluster)
        if doc:
            # 写入 kb/pending/
            KB_PENDING.mkdir(parents=True, exist_ok=True)
            slug = _slugify(keyword)
            out_path = KB_PENDING / f"kb-auto-{slug}.yaml"

            import yaml as _yaml
            out_path.write_text(
                _yaml.dump(doc, allow_unicode=True, default_flow_style=False, sort_keys=False, width=120),
                encoding="utf-8",
            )
            print(f"  [OK] Written: {out_path}")
            generated.append({
                "keyword": keyword,
                "file": str(out_path),
                "fail_rate": cluster["fail_rate"],
            })
        else:
            print(f"  [SKIP] Failed to generate")

        # 请求间冷却（避免 API 限流）
        if i < len(eligible):
            time.sleep(2)

    return generated


# ── 主入口 ──

def main():
    ap = argparse.ArgumentParser(description="KB 补充文档生成器")
    ap.add_argument("--analysis", default="eval/results/failure_analysis.json",
                    help="失败聚类分析 JSON 文件")
    ap.add_argument("--out", default="kb/pending",
                    help="输出目录（pending YAML 文件）")
    ap.add_argument("--min-fail-rate", type=float, default=0.5,
                    help="最小失败率阈值（默认 0.5）")
    ap.add_argument("--dry-run", action="store_true",
                    help="仅预览，不调用 LLM 也不写入文件")
    args = ap.parse_args()

    global KB_PENDING
    KB_PENDING = Path(args.out)

    with open(args.analysis, encoding="utf-8") as fh:
        data = json.load(fh)
    clusters = data.get("clusters", [])

    print(f"[kb_generator] Loaded {len(clusters)} clusters from {args.analysis}")
    summary = data.get("summary", {})
    print(f"  Critical: {summary.get('n_critical', 0)}")
    print(f"  Severe:   {summary.get('n_severe', 0)}")

    generated = generate_all(clusters, min_fail_rate=args.min_fail_rate, dry_run=args.dry_run)

    if generated:
        print(f"\n[kb_generator] Generated {len(generated)} KB docs:")
        for g in generated:
            print(f"  {g['keyword']} → {g['file']}")
        print(f"\n[kb_generator] ALL docs written to kb/pending/ — must be manually reviewed before moving to kb/active/")
    elif not args.dry_run:
        print("\n[kb_generator] No docs generated.")


if __name__ == "__main__":
    main()
