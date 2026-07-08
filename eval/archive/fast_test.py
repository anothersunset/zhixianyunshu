#!/usr/bin/env python3
"""Quick migration smoke test for local backend.

This helper is intentionally lightweight. Formal metrics should use
`python -m eval.run_eval`.
"""
from __future__ import annotations

import concurrent.futures
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

DATASETS = [
    "mysql_opengauss",
    "mysql_postgres",
    "oracle_pg",
    "sqlserver_opengauss",
    "sqlserver_postgres",
]
BACKEND_URL = "http://localhost:8080"
RESULTS_DIR = Path("eval/results")


def load_cases() -> list[tuple[dict[str, Any], str]]:
    cases: list[tuple[dict[str, Any], str]] = []
    for dataset in DATASETS:
        with open(f"eval/datasets/{dataset}.jsonl", encoding="utf-8-sig") as fh:
            for line in fh:
                if line.strip():
                    cases.append((json.loads(line), dataset))
    return cases


def test_case(case: dict[str, Any], mode: str) -> dict[str, Any]:
    start = time.time()
    payload = {
        "source_sql": case["source_sql"],
        "pair": case["pair"],
        "retrieval": "full" if mode == "full" else "bm25",
        "fast": mode == "fast",
    }
    timeout = 180 if mode == "full" else 60
    try:
        resp = requests.post(f"{BACKEND_URL}/migrate", json=payload, timeout=timeout)
        resp.raise_for_status()
        body = resp.json()
        return {
            "id": case["id"],
            "pair": case["pair"],
            "success": True,
            "target_sql": body.get("target_sql", ""),
            "response_time": time.time() - start,
            "mode": mode,
            "error": None,
        }
    except Exception as exc:
        return {
            "id": case["id"],
            "pair": case["pair"],
            "success": False,
            "target_sql": "",
            "response_time": None,
            "mode": mode,
            "error": str(exc),
        }


def run_mode(all_cases: list[tuple[dict[str, Any], str]], mode: str, workers: int) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {dataset: [] for dataset in DATASETS}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(test_case, case, mode): dataset for case, dataset in all_cases}
        for future in concurrent.futures.as_completed(futures):
            dataset = futures[future]
            result = future.result()
            grouped.setdefault(dataset, []).append(result)
            status = "OK" if result["success"] else "FAIL"
            if result["response_time"] is None:
                print(f"[{status}] {result['id']} - {result['error'][:80]}")
            else:
                print(f"[{status}] {result['id']} - {result['response_time']:.2f}s")
    return grouped


def summarize(grouped: dict[str, list[dict[str, Any]]], mode: str) -> None:
    print(f"\n=== {mode} summary ===")
    for dataset in DATASETS:
        rows = grouped.get(dataset, [])
        total = len(rows)
        ok = sum(1 for row in rows if row["success"])
        avg = sum(row["response_time"] for row in rows if row["response_time"] is not None) / total if total else 0
        rate = ok / total * 100 if total else 0
        print(f"{dataset}: {ok}/{total} ({rate:.1f}%) | avg={avg:.2f}s")


def main() -> None:
    all_cases = load_cases()
    print(f"Total cases: {len(all_cases)}")
    started_at = datetime.now()
    fast_results = run_mode(all_cases, "fast", workers=10)
    full_results = run_mode(all_cases, "full", workers=5)
    summarize(fast_results, "fast")
    summarize(full_results, "full")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = RESULTS_DIR / f"fast_test_{timestamp}.json"
    out.write_text(json.dumps({
        "start_time": started_at.isoformat(),
        "fast_results": fast_results,
        "full_results": full_results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResults saved to: {out}")


if __name__ == "__main__":
    main()
