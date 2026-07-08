"""全量实验前的预检脚本 — 验证所有关键机制正常工作。

用法: python -m eval.preflight [--pair mysql_opengauss]

检查项:
1. 后端健康检查 (port 8080)
2. RAG 服务健康检查 (port 8001) + 内存监控
3. 单 case 端到端测试 (migration → SQL → report)
4. Checkpoint 写入测试 (验证 on_progress 回调)
5. Judge 服务测试 (如果启用)
6. 检索模式测试 (验证 bm25/vector 都能返回结果)
7. RAG 能力探针 (验证 dense/rerank/graphrag 是真实实现而非降级占位)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import requests

from eval.migration_client import MigrationClient


def check_backend(base_url: str) -> bool:
    """检查后端是否健康。"""
    print("[1/7] 后端健康检查...", end=" ", flush=True)
    try:
        r = requests.get(f"{base_url}/actuator/health", timeout=10)
        if r.status_code == 200:
            print("OK", flush=True)
            return True
        print(f"FAIL (status={r.status_code})", flush=True)
        return False
    except Exception as e:
        print(f"FAIL ({e})", flush=True)
        return False


def check_rag(rag_url: str) -> bool:
    """检查 RAG 服务是否健康 + 内存。"""
    print("[2/7] RAG 服务健康检查...", end=" ", flush=True)
    try:
        r = requests.get(f"{rag_url}/health", timeout=10)
        if r.status_code == 200:
            data = r.json()
            mem = data.get("memory_mb", 0)
            print(f"OK (memory={mem:.0f}MB)", flush=True)
            if mem > 3000:
                print("  [WARN] 内存超过 3GB，建议重启 RAG", flush=True)
            return True
        print(f"FAIL (status={r.status_code})", flush=True)
        return False
    except Exception as e:
        print(f"FAIL ({e})", flush=True)
        return False


def check_single_case(client, pair: str, fast: bool) -> bool:
    """单 case 端到端测试。"""
    print("[3/7] 单 case 端到端测试...", end=" ", flush=True)
    try:
        # 加载一个 case
        from eval.run_eval import load_dataset
        cases = load_dataset("eval/datasets", pair)
        if not cases:
            print(f"FAIL (no cases for pair={pair})", flush=True)
            return False
        c = cases[0]
        res = client.run_migration(
            source_sql=c["source_sql"], pair=c["pair"],
            retrieval="full", fast=fast
        )
        if res.target_sql:
            print(f"OK (sql_len={len(res.target_sql)}, risk={res.risk_level})", flush=True)
            return True
        print(f"FAIL (empty target_sql)", flush=True)
        return False
    except Exception as e:
        print(f"FAIL ({e})", flush=True)
        return False


def check_checkpoint() -> bool:
    """验证 checkpoint 写入机制。"""
    print("[4/7] Checkpoint 写入测试...", end=" ", flush=True)
    try:
        from eval.run_eval import evaluate, summarize, load_dataset
        from eval.migration_client import MigrationClient

        client = MigrationClient(cooldown=0)
        cases = load_dataset("eval/datasets", "mysql_opengauss")[:5]  # 取 5 个 case 触发 checkpoint

        ckpt_path = "/tmp/preflight_checkpoint_test.json"
        if os.path.exists(ckpt_path):
            os.unlink(ckpt_path)

        rows = evaluate(cases, "bm25", client, fast=True, checkpoint_path=ckpt_path)

        # 检查 checkpoint 文件
        if os.path.exists(ckpt_path):
            with open(ckpt_path, encoding="utf-8") as fh:
                data = json.load(fh)
            ckpt_n = len(data.get("rows", []))
            os.unlink(ckpt_path)
            if ckpt_n == len(rows) and len(rows) == 5:
                print(f"OK ({ckpt_n} rows checkpointed)", flush=True)
                return True
            print(f"FAIL (expected 5 rows, checkpoint has {ckpt_n}, evaluate returned {len(rows)})", flush=True)
            return False
        print(f"FAIL (checkpoint file not created at {ckpt_path})", flush=True)
        return False
    except Exception as e:
        print(f"FAIL ({e})", flush=True)
        return False


def check_judge(judge_url: str) -> bool:
    """检查 Judge 服务。"""
    print("[5/7] Judge 服务测试...", end=" ", flush=True)
    try:
        from eval.judge import LLMJudge
        judge = LLMJudge()
        ok = judge.sql_semantically_equal(
            "SELECT IFNULL(name, 'x') FROM users",
            "SELECT COALESCE(name, 'x') FROM users",
            "mysql"
        )
        if ok:
            print("OK (IFNULL≈COALESCE)", flush=True)
            return True
        print("FAIL (should be equivalent)", flush=True)
        return False
    except Exception as e:
        err_msg = str(e)
        if "JUDGE_API_KEY" in err_msg or "api_key" in err_msg.lower():
            print(f"SKIP (JUDGE_API_KEY 未设置, --use-judge 不可用)", flush=True)
            return True  # Not a blocker, just skip judge
        print(f"FAIL ({e})", flush=True)
        return False


def check_retrieval_modes(rag_url: str) -> bool:
    """验证各检索模式能返回结果。"""
    print("[6/7] 检索模式测试...", flush=True)
    modes = ["bm25", "vector", "vector_rerank", "crag", "full"]
    all_ok = True
    for mode in modes:
        try:
            r = requests.post(
                f"{rag_url}/retrieve",
                json={"query": "Oracle DECODE function", "top_k": 3, "mode": mode},
                timeout=30,
            )
            if r.status_code == 200:
                items = r.json().get("items", [])
                print(f"  {mode}: OK ({len(items)} items)", flush=True)
            else:
                print(f"  {mode}: FAIL (status={r.status_code})", flush=True)
                all_ok = False
        except Exception as e:
            print(f"  {mode}: FAIL ({e})", flush=True)
            all_ok = False
    return all_ok


def check_capabilities(rag_url: str, allow_degraded: bool) -> bool:
    """实验条件探针：消融的前提是每一档能力真实在线。

    embedder 不可用时会降级为 SHA-256 hash 伪向量（纯噪声通道），reranker 不可用时
    静默 noop——服务照常返回结果、实验照样跑完，但 vector/rerank/full 各档全部失真。
    检索模式测试（第 6 项）只验证"有返回"，测不出这种降级，必须读 capabilities。
    """
    print("[7/7] RAG 能力探针 (capabilities)...", flush=True)
    try:
        r = requests.post(
            f"{rag_url}/retrieve",
            json={"query": "capability probe", "top_k": 1, "mode": "bm25"},
            timeout=30,
        )
        r.raise_for_status()
        caps = r.json().get("capabilities", {})
    except Exception as e:
        print(f"  FAIL ({e})", flush=True)
        return False
    print(f"  bm25={caps.get('bm25')} dense={caps.get('dense')} rerank={caps.get('rerank')} "
          f"graphrag={caps.get('graphrag')} docs={caps.get('docs')}", flush=True)
    print(f"  embed_model={caps.get('embed_model')} rerank_model={caps.get('rerank_model')}", flush=True)
    degraded = [k for k in ("dense", "rerank", "graphrag") if not caps.get(k)]
    if degraded:
        print(f"  [DEGRADED] {', '.join(degraded)} 处于降级态：vector 档=hash 伪向量 / rerank 档=noop，"
              "消融梯度会失真甚至递减。", flush=True)
        print("  修复: pip install -r zhiqian/rag/requirements-ml.txt 并确认 Qdrant 在线后重启 RAG。", flush=True)
        if allow_degraded:
            print("  (--allow-degraded 已指定，仅冒烟用途放行)", flush=True)
            return True
        return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", default="mysql_opengauss")
    ap.add_argument("--fast", action="store_true", default=True)
    ap.add_argument("--backend-url", default="http://localhost:8080")
    ap.add_argument("--rag-url", default="http://localhost:8001")
    ap.add_argument("--cooldown", type=float, default=5)
    ap.add_argument("--allow-degraded", action="store_true",
                    help="允许 RAG 能力降级时通过预检（仅冒烟测试；消融实验严禁使用）")
    args = ap.parse_args()

    print("=" * 60, flush=True)
    print("全量实验预检 (Preflight Check)", flush=True)
    print("=" * 60, flush=True)

    results = {}
    results["backend"] = check_backend(args.backend_url)
    results["rag"] = check_rag(args.rag_url)

    if not results["backend"]:
        print("\n❌ 后端不可用，无法继续", flush=True)
        sys.exit(1)

    client = MigrationClient(base_url=args.backend_url, cooldown=args.cooldown)
    results["single_case"] = check_single_case(client, args.pair, args.fast)
    results["checkpoint"] = check_checkpoint()
    results["judge"] = check_judge(args.backend_url)
    results["retrieval"] = check_retrieval_modes(args.rag_url)
    results["capabilities"] = check_capabilities(args.rag_url, args.allow_degraded)

    print("\n" + "=" * 60, flush=True)
    print("预检结果汇总:", flush=True)
    all_pass = True
    for name, ok in results.items():
        status = "[PASS]" if ok else "[FAIL]"
        print(f"  {name}: {status}", flush=True)
        if not ok:
            all_pass = False

    print("=" * 60, flush=True)
    if all_pass:
        print("[PASS] 全部通过，可以安全运行全量实验", flush=True)
    else:
        print("[FAIL] 有检查项失败，请修复后再跑全量实验", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
