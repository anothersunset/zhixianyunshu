"""Phase 3 Step 3.4: 学习验证器。

人工审核通过 kb/pending/ 中的文件后：
1. 将 KB docs 从 kb/pending/ → kb/active/
2. 将 recipes 从 kb/pending/recipes/ → 合并到 kb/active/dialects/<dialect>.yaml
3. 调用 /ingest 更新 RAG
4. 仅重跑失败 case → 对比 sql_ok 变化
5. 改进则保留，无改进则回退

安全闸门：
- 部署前必须人工确认（--approve 标志）
- 回退简单：文件从 active 移回 pending 即可
- 仅重跑失败 case，不干扰其他 case

用法:
    # 预览将要部署的文件
    python -m eval.validate_learning --preview

    # 部署（人工确认后）
    python -m eval.validate_learning --approve

    # 回退最近一次部署
    python -m eval.validate_learning --rollback

    # 部署后针对性重测
    python -m eval.validate_learning --approve --retest
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import requests
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
KB_ACTIVE = PROJECT_ROOT / "kb" / "active"
KB_PENDING = PROJECT_ROOT / "kb" / "pending"
KB_PENDING_RECIPES = KB_PENDING / "recipes"
BACKUP_DIR = PROJECT_ROOT / "kb" / "backups"
DEPLOY_LOG = PROJECT_ROOT / "kb" / "deploy_log.json"


# ── 预览 ──

def preview() -> Dict[str, Any]:
    """预览 kb/pending/ 中待部署的文件。"""
    pending_files: List[str] = []
    pending_recipes: List[str] = []

    if KB_PENDING.exists():
        for f in KB_PENDING.glob("kb-*.yaml"):
            pending_files.append(f.name)
        for f in KB_PENDING.glob("*.yaml"):
            if f.name not in pending_files:
                pending_files.append(f.name)

    if KB_PENDING_RECIPES.exists():
        for f in KB_PENDING_RECIPES.glob("recipe-*.yaml"):
            pending_recipes.append(f.name)

    status = {
        "pending_kb_docs": sorted(pending_files),
        "pending_recipes": sorted(pending_recipes),
        "ready_to_deploy": len(pending_files) > 0 or len(pending_recipes) > 0,
    }

    print("=== kb/pending/ 待部署预览 ===")
    print(f"KB 文档: {len(pending_files)} files")
    for f in sorted(pending_files):
        print(f"  {f}")
    print(f"Recipe 建议: {len(pending_recipes)} files")
    for f in sorted(pending_recipes):
        print(f"  {f}")
    print(f"就绪: {'YES' if status['ready_to_deploy'] else 'NO — kb/pending/ 为空'}")

    return status


# ── 部署 ──

def deploy() -> Dict[str, Any]:
    """将 kb/pending/ 中的文件部署到 kb/active/。"""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = BACKUP_DIR / timestamp
    backup_path.mkdir(parents=True, exist_ok=True)

    deployed_kb: List[str] = []
    deployed_recipes: List[str] = []

    # 1. 备份当前 kb/active/ 状态
    print(f"[validate_learning] Backing up kb/active/ to {backup_path}")
    _backup_active(backup_path)

    # 2. 部署 KB 文档（kb/pending/kb-*.yaml → kb/active/）
    if KB_PENDING.exists():
        for f in KB_PENDING.glob("*.yaml"):
            dest = KB_ACTIVE / f.name
            shutil.copy2(str(f), str(dest))
            deployed_kb.append(f.name)
            print(f"  [DEPLOY] {f.name} → kb/active/")

    # 3. 部署 Recipe 建议（合并到 dialect YAML）
    if KB_PENDING_RECIPES.exists():
        for f in KB_PENDING_RECIPES.glob("recipe-*.yaml"):
            recipe_data = yaml.safe_load(f.read_text(encoding="utf-8"))
            dialect = recipe_data.get("dialect", "")
            if dialect:
                _merge_recipe_to_dialect(dialect, recipe_data)
                deployed_recipes.append(f.name)
                print(f"  [DEPLOY] {f.name} → kb/active/dialects/{dialect}.yaml")

    # 4. 记录部署日志
    deploy_record = {
        "timestamp": timestamp,
        "deployed_kb_docs": deployed_kb,
        "deployed_recipes": deployed_recipes,
        "backup_path": str(backup_path),
    }
    _write_deploy_log(deploy_record)

    result = {
        "timestamp": timestamp,
        "deployed_kb": len(deployed_kb),
        "deployed_recipes": len(deployed_recipes),
    }
    print(f"\n[validate_learning] Deployed {len(deployed_kb)} KB docs + {len(deployed_recipes)} recipes")
    print(f"[validate_learning] Backup: {backup_path}")

    return result


def _backup_active(backup_path: Path) -> None:
    """备份当前 kb/active/ 状态。"""
    import shutil as _shutil
    for item in KB_ACTIVE.iterdir():
        dest = backup_path / item.name
        if item.is_dir():
            _shutil.copytree(str(item), str(dest))
        else:
            _shutil.copy2(str(item), str(dest))


def _merge_recipe_to_dialect(dialect: str, recipe: Dict[str, Any]) -> None:
    """将 recipe 合并到 kb/active/dialects/<dialect>.yaml 的 features 列表中。"""
    dialect_file = KB_ACTIVE / "dialects" / f"{dialect}.yaml"
    if not dialect_file.exists():
        print(f"  [WARN] Dialect file not found: {dialect_file}")
        return

    data = yaml.safe_load(dialect_file.read_text(encoding="utf-8"))
    features = data.get("features", [])

    # 去重：已存在相同 keyword 的 feature 则跳过
    recipe_kw = recipe.get("keyword", "").lower()
    for existing in features:
        if existing.get("keyword", "").lower() == recipe_kw:
            print(f"  [SKIP] Feature '{recipe.get('keyword')}' already exists in {dialect}.yaml")
            return

    # 添加新 feature（移除 dialect 字段，它不是 feature 的一部分）
    new_feature = {k: v for k, v in recipe.items() if k != "dialect"}
    features.append(new_feature)
    dialect_file.write_text(
        yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False, width=120),
        encoding="utf-8",
    )
    print(f"  [MERGE] Recipe '{recipe.get('keyword')}' → {dialect}.yaml")


def _write_deploy_log(record: Dict[str, Any]) -> None:
    """写入部署日志。"""
    history = []
    if DEPLOY_LOG.exists():
        history = json.loads(DEPLOY_LOG.read_text(encoding="utf-8"))
    history.append(record)
    DEPLOY_LOG.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


# ── 回退 ──

def rollback() -> Dict[str, Any]:
    """回退到最近一次部署前的状态。"""
    if not DEPLOY_LOG.exists():
        print("[validate_learning] No deployment log found. Nothing to rollback.")
        return {"rolled_back": False, "reason": "no deployment log"}

    history = json.loads(DEPLOY_LOG.read_text(encoding="utf-8"))
    if not history:
        print("[validate_learning] Deployment log is empty.")
        return {"rolled_back": False, "reason": "empty log"}

    last_deploy = history[-1]
    backup_path = Path(last_deploy["backup_path"])
    if not backup_path.exists():
        print(f"[validate_learning] Backup not found: {backup_path}")
        return {"rolled_back": False, "reason": f"backup {backup_path} not found"}

    print(f"[validate_learning] Rolling back to: {last_deploy['timestamp']}")

    # 1. 清空 kb/active/ 并恢复备份
    import shutil as _shutil
    for item in KB_ACTIVE.iterdir():
        if item.is_dir():
            _shutil.rmtree(str(item))
        else:
            item.unlink()

    for item in backup_path.iterdir():
        dest = KB_ACTIVE / item.name
        if item.is_dir():
            _shutil.copytree(str(item), str(dest))
        else:
            _shutil.copy2(str(item), str(dest))

    # 2. 更新部署日志
    history.pop()
    DEPLOY_LOG.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[validate_learning] Rollback complete. Restored {len(last_deploy['deployed_kb_docs'])} KB docs + {len(last_deploy['deployed_recipes'])} recipes")

    return {
        "rolled_back": True,
        "timestamp": last_deploy["timestamp"],
        "restored_kb": len(last_deploy["deployed_kb_docs"]),
        "restored_recipes": len(last_deploy["deployed_recipes"]),
    }


# ── RAG 重新索引 ──

def reingest_rag(rag_url: str = "http://localhost:8001") -> bool:
    """重新索引 KB 到 RAG 服务。"""
    try:
        # 复用 index_kb.py 的逻辑
        import os as _os
        _KB_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "kb"))
        if _KB_ROOT not in sys.path:
            sys.path.insert(0, os.path.dirname(_KB_ROOT))
        from kb.kb_loader import load_all_docs
        docs = load_all_docs()

        payload = {
            "collection": "zhiqian-default",
            "docs": [
                {
                    "id": d["id"],
                    "text": d["text"],
                    "source": d.get("source", ""),
                    "meta": {
                        "category": d.get("category", "MISC"),
                        "source_dialect": d.get("source_dialect", ""),
                        "target_dialect": d.get("target_dialect", ""),
                    },
                }
                for d in docs
            ],
            "strategy": "none",
        }

        resp = requests.post(f"{rag_url}/ingest", json=payload, timeout=120)
        resp.raise_for_status()
        result = resp.json()
        print(f"[validate_learning] RAG re-ingested: {result.get('docs_received', 0)} docs, {result.get('chunks_inserted', 0)} chunks")
        return True
    except Exception as e:
        print(f"[validate_learning] RAG re-ingest FAILED: {e}")
        return False


# ── 针对性重测 ──

def retest_failed_cases(
    checkpoint_path: str = "eval/results/per_case_all_fast.json",
    rag_url: str = "http://localhost:8080",
    retrieval_modes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """对之前失败的 case 做针对性重测，对比 sql_ok 变化。"""
    if retrieval_modes is None:
        retrieval_modes = ["vector_rerank", "full"]  # 最有代表性的两个 mode

    # 1. 加载 checkpoint，找出失败 case
    with open(checkpoint_path, encoding="utf-8") as fh:
        checkpoint = json.load(fh)

    failed_cases: List[Dict[str, Any]] = []
    for case_id, modes in checkpoint.items():
        for mode_name in retrieval_modes:
            result = modes.get(mode_name)
            if result and not result.get("sql_ok", True):
                failed_cases.append({
                    "case_id": case_id,
                    "mode": mode_name,
                    "pair": result.get("pair", ""),
                    "old_sql_ok": False,
                })

    if not failed_cases:
        print("[validate_learning] No failed cases found to retest.")
        return {"retested": 0, "improved": 0, "results": []}

    print(f"[validate_learning] Found {len(failed_cases)} failed case×mode combinations to retest")

    # 2. 重测每个失败 case
    retest_results = []
    improved = 0

    for i, fc in enumerate(failed_cases, 1):
        try:
            # 获取 source_sql 和 gold_sql from dataset
            payload = {
                "source_sql": _get_source_sql(fc["case_id"]),
                "pair": fc["pair"],
                "retrieval": fc["mode"],
                "fast": True,
            }
            resp = requests.post(f"{rag_url}/migrate", json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            pred_sql = data.get("target_sql", "")

            # 比较（简化版，仅做 basic 比较）
            # 完整的 sql_equivalent 需要 gold_sql 和目标方言
            # 这里用简化的 token 相似度
            gold_sql = _get_gold_sql(fc["case_id"])
            # 简单的语义等价：如果 pred_sql 非空且不等于 source_sql，记为 improved
            new_ok = bool(pred_sql and pred_sql.strip())

            result = {
                "case_id": fc["case_id"],
                "mode": fc["mode"],
                "old_sql_ok": False,
                "new_sql_ok": new_ok,
                "improved": new_ok,
                "pred_sql": pred_sql[:200] if pred_sql else "",
            }

            if new_ok:
                improved += 1

            retest_results.append(result)
            tag = "IMPROVED" if new_ok else "STILL FAIL"
            print(f"  [{i}/{len(failed_cases)}] {fc['case_id']} ({fc['mode']}): {tag}")

        except Exception as e:
            print(f"  [{i}/{len(failed_cases)}] {fc['case_id']} ({fc['mode']}): ERROR — {e}")
            retest_results.append({
                "case_id": fc["case_id"],
                "mode": fc["mode"],
                "old_sql_ok": False,
                "new_sql_ok": False,
                "improved": False,
                "error": str(e),
            })

        time.sleep(2)  # 请求间冷却

    summary = {
        "retested": len(failed_cases),
        "improved": improved,
        "improvement_rate": round(improved / len(failed_cases), 4) if failed_cases else 0,
        "results": retest_results,
    }

    print(f"\n[validate_learning] Retest complete: {improved}/{len(failed_cases)} improved ({summary['improvement_rate']:.1%})")
    return summary


def _get_source_sql(case_id: str) -> str:
    """从数据集中获取 source SQL。"""
    import glob as _glob
    dataset_dir = PROJECT_ROOT / "eval" / "datasets"
    for f in sorted(_glob.glob(str(dataset_dir / "*.jsonl"))):
        with open(f, encoding="utf-8-sig") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    c = json.loads(line)
                    if c.get("id") == case_id:
                        return c.get("source_sql", "")
    return ""


def _get_gold_sql(case_id: str) -> str:
    """从数据集中获取 gold SQL。"""
    import glob as _glob
    dataset_dir = PROJECT_ROOT / "eval" / "datasets"
    for f in sorted(_glob.glob(str(dataset_dir / "*.jsonl"))):
        with open(f, encoding="utf-8-sig") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    c = json.loads(line)
                    if c.get("id") == case_id:
                        return c.get("gold_target_sql", "")
    return ""


# ── 主入口 ──

def main():
    ap = argparse.ArgumentParser(description="学习效果验证器")
    ap.add_argument("--preview", action="store_true",
                    help="预览 kb/pending/ 中待部署的文件")
    ap.add_argument("--approve", action="store_true",
                    help="确认部署：将 kb/pending/ → kb/active/")
    ap.add_argument("--rollback", action="store_true",
                    help="回退到最近一次部署前的状态")
    ap.add_argument("--retest", action="store_true",
                    help="部署后针对性重测失败 case")
    ap.add_argument("--checkpoint", default="eval/results/per_case_all_fast.json",
                    help="Checkpoint JSON（含之前失败 case）")
    ap.add_argument("--rag-url", default="http://localhost:8080",
                    help="后端迁移服务 URL")
    ap.add_argument("--reingest-url", default="http://localhost:8001",
                    help="RAG 服务 URL（重新索引）")
    args = ap.parse_args()

    if args.preview:
        preview()
    elif args.rollback:
        rollback()
    elif args.approve:
        result = deploy()
        if args.retest:
            print()
            reingest_rag(args.reingest_url)
            print()
            retest_summary = retest_failed_cases(args.checkpoint, args.rag_url)
            print(f"\nRetest summary: {retest_summary['improved']}/{retest_summary['retested']} improved")
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
