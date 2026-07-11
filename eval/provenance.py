"""Reproducible metadata for deterministic and judged evaluation runs."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def dataset_fingerprint(cases: list[dict[str, Any]]) -> str:
    payload = json.dumps(cases, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _git(repo_root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            [
                "git",
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.excludesfile=.gitignore",
                *args,
            ],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def build_run_metadata(
    *,
    cases: list[dict[str, Any]],
    config: dict[str, Any],
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = (repo_root or Path(__file__).resolve().parents[1]).resolve()
    git_sha = _git(root, "rev-parse", "HEAD")
    dirty_output = _git(root, "status", "--porcelain", "--untracked-files=no")
    return {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git": {"sha": git_sha, "dirty": None if dirty_output is None else bool(dirty_output)},
        "dataset": {"cases": len(cases), "sha256": dataset_fingerprint(cases)},
        "runtime": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "models": {
            "migration": os.getenv("LLM_CHAT_MODEL"),
            "reasoner": os.getenv("LLM_REASONER_MODEL"),
            "judge": config.get("judge_model"),
        },
        "config": config,
        "cost_contract": {
            "currency": "USD",
            "source": "backend_reported_only",
            "note": "No price is inferred when the backend does not report cost.",
        },
    }
