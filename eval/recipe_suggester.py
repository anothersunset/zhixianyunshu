"""Phase 3 Step 3.3: 配方建议器。

对 failed_rate >= 0.8 且 >= 3 个 mode 失败的聚类，用 LLM 生成完整的
RegisteredFeature YAML 条目（含 few-shot、step_by_step、pitfalls）。

输出到 kb/pending/recipes/<feature>.yaml，待人工审核后合并到 kb/active/dialects/<dialect>.yaml。

安全闸门：仅写入 kb/pending/recipes/，绝不自动修改 kb/active/。

用法:
    python -m eval.recipe_suggester \
        --analysis eval/results/failure_analysis.json \
        --out kb/pending/recipes
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

PROJECT_ROOT = Path(__file__).resolve().parent.parent
KB_PENDING_RECIPES = PROJECT_ROOT / "kb" / "pending" / "recipes"


def _llm_chat(prompt: str, system: str = "You are a senior database migration expert.") -> str:
    """调用 LLM。"""
    api_key = os.environ.get("LLM_API_KEY", "")
    base_url = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/v1")
    model = os.environ.get("LLM_CHAT_MODEL", "deepseek-chat")

    if not api_key:
        raise RuntimeError("LLM_API_KEY not set")

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
    return resp.json()["choices"][0]["message"]["content"]


def _slugify(keyword: str) -> str:
    return keyword.lower().replace("(", "-").replace(")", "").replace(" ", "-").replace("_", "-")


def _infer_dialect(keyword: str) -> str:
    kw = keyword.lower()
    oracle_kw = {
        "rownum", "connect by", "start with", "merge into", "months_between(",
        "decode(", "nvl(", "nvl2(", "sysdate", "from dual", "(+)", "pivot(", "unpivot(",
        "listagg(", "regexp_substr(", "add_months(", "to_char(", "to_date(",
        "instr(", "initcap(", "user", "uid", "to_number(", "substr(",
        "systimestamp", "to_timestamp(", "regexp_replace(", "regexp_like(",
        "timestamp_trunc(", "trunc(",
    }
    if kw in oracle_kw:
        return "oracle"
    return "mysql"


def generate_recipe(cluster: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """为单个失败聚类生成 RegisteredFeature YAML 条目。"""
    keyword = cluster["keyword"]
    mapping = cluster["mapping"]
    category = cluster["category"]
    fail_rate = cluster["fail_rate"]
    failing_modes = cluster.get("failing_modes", [])
    samples = cluster.get("sample_cases", [])[:3]

    sample_text = ""
    for i, s in enumerate(samples, 1):
        sample_text += f"""
Sample {i}:
  Source SQL: {s.get('source_sql', 'N/A')}
  Gold (expected): {s.get('gold_sql', 'N/A')}
  Pred (actual): {s.get('pred_sql', 'N/A')}
"""

    prompt = f"""You are a senior database migration agent specializing in Oracle/MySQL to PostgreSQL conversion.
A specific conversion pattern is repeatedly failing across multiple retrieval modes.

PATTERN: {keyword} → {mapping}
FAILURE RATE: {fail_rate:.0%} (fails in modes: {', '.join(failing_modes)})

FAILED EXAMPLES:
{sample_text}

TASK: Generate a complete RegisteredFeature YAML entry that will be injected into the LLM prompt
as a detailed conversion recipe. The recipe MUST include:

1. A clear few_shot_source example (realistic Oracle/MySQL SQL using this construct)
2. A CORRECT few_shot_target example (correct PostgreSQL SQL)
3. Step-by-step conversion guide (numbered, specific)
4. Common pitfalls that LLMs make when converting this (specific errors to AVOID)

IMPORTANT PRINCIPLES:
- The recipe must be SPECIFIC enough to prevent the exact errors shown in the samples above
- The step_by_step should be a literal checklist the LLM can follow
- Pitfalls should describe the WRONG behavior and say DO NOT do it
- The mapping field describes the general approach

Output in YAML format:
```yaml
keyword: {keyword}
mapping: {mapping}
category: {category}
is_recipe: true
construct_name: <descriptive name like "MONTHS_BETWEEN Date Difference">
few_shot_source: |
  <realistic source SQL>
few_shot_target: |
  <correct target SQL>
step_by_step: |
  1. ...
  2. ...
pitfalls:
  - <pitfall 1>
  - <pitfall 2>
```

Generate ONLY the YAML block. Copy the exact format above. Keep step_by_step concise (3-5 steps).
"""

    try:
        reply = _llm_chat(prompt)
        yaml_text = _extract_yaml(reply)
        if yaml_text:
            import yaml as _yaml
            return _yaml.safe_load(yaml_text)
    except Exception as e:
        print(f"  [ERROR] Failed to generate recipe for {keyword}: {e}")
    return None


def _extract_yaml(text: str) -> str:
    import re
    m = re.search(r'```(?:yaml)?\s*\n?(.*?)```', text, re.DOTALL)
    if m:
        return m.group(1).strip()
    m = re.search(r'(keyword:.*)', text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text.strip()


def generate_all_recipes(
    clusters: List[Dict[str, Any]],
    dry_run: bool = False,
) -> List[Dict[str, Any]]:
    """为符合条件的聚类生成配方建议。"""
    # 筛选条件: fail_rate >= 0.8 且 >= 3 modes
    eligible = [c for c in clusters if c["fail_rate"] >= 0.8 and c.get("mode_count", 0) >= 3]

    print(f"[recipe_suggester] {len(eligible)}/{len(clusters)} clusters eligible "
          f"(fail_rate >= 0.8 & >= 3 modes)")
    if dry_run:
        print("[recipe_suggester] DRY RUN — 不会写入文件")
        for c in eligible:
            print(f"  Would generate recipe: {c['keyword']} (fail_rate={c['fail_rate']:.0%}, modes={c.get('mode_count', 0)})")
        return []

    generated = []
    for i, cluster in enumerate(eligible, 1):
        keyword = cluster["keyword"]
        dialect = _infer_dialect(keyword)
        print(f"\n[{i}/{len(eligible)}] Generating recipe for: {keyword} (dialect={dialect})")

        recipe = generate_recipe(cluster)
        if recipe:
            # 确保有 dialect 字段
            if "dialect" not in recipe:
                recipe["dialect"] = dialect

            KB_PENDING_RECIPES.mkdir(parents=True, exist_ok=True)
            slug = _slugify(keyword)
            out_path = KB_PENDING_RECIPES / f"recipe-{slug}.yaml"

            import yaml as _yaml
            out_path.write_text(
                _yaml.dump(recipe, allow_unicode=True, default_flow_style=False, sort_keys=False, width=120),
                encoding="utf-8",
            )
            print(f"  [OK] Written: {out_path}")
            generated.append({
                "keyword": keyword,
                "dialect": dialect,
                "file": str(out_path),
            })
        else:
            print(f"  [SKIP] Failed to generate recipe")

        if i < len(eligible):
            time.sleep(2)

    return generated


def main():
    ap = argparse.ArgumentParser(description="Recipe 建议生成器")
    ap.add_argument("--analysis", default="eval/results/failure_analysis.json",
                    help="失败聚类分析 JSON")
    ap.add_argument("--out", default="kb/pending/recipes",
                    help="输出目录")
    ap.add_argument("--dry-run", action="store_true",
                    help="仅预览，不调用 LLM 也不写入文件")
    args = ap.parse_args()

    global KB_PENDING_RECIPES
    KB_PENDING_RECIPES = Path(args.out)

    with open(args.analysis, encoding="utf-8") as fh:
        data = json.load(fh)
    clusters = data.get("clusters", [])

    print(f"[recipe_suggester] Loaded {len(clusters)} clusters from {args.analysis}")

    generated = generate_all_recipes(clusters, dry_run=args.dry_run)

    if generated:
        print(f"\n[recipe_suggester] Generated {len(generated)} recipe suggestions:")
        for g in generated:
            print(f"  {g['keyword']} ({g['dialect']}) → {g['file']}")
        print(f"\n[recipe_suggester] ALL recipes in kb/pending/recipes/ — manual review required before merging to kb/active/dialects/")
    elif not args.dry_run:
        print("\n[recipe_suggester] No recipes generated.")


if __name__ == "__main__":
    main()
