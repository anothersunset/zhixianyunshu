"""rag_watchdog 端口一致性: 默认 8001 (与 eval/rag_watchdog.py、preflight、Dockerfile 对齐),
并保留 RAG_WATCHDOG_PORT 环境变量覆盖能力。
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from unittest.mock import patch

WATCHDOG_PATH = Path(__file__).resolve().parents[1] / "rag_watchdog.py"


def _load_watchdog_module(name: str):
    spec = importlib.util.spec_from_file_location(name, WATCHDOG_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_port_is_8001_matching_eval_side_and_docker():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("RAG_WATCHDOG_PORT", None)
        module = _load_watchdog_module("rag_watchdog_default_port")
    assert module.RAG_PORT == 8001
    assert module.HEALTH_URL == "http://127.0.0.1:8001/health"
    # 启动命令端口与监控端口必须同源, 避免监控 A 端口却拉起 B 端口服务
    assert "--port" in module.RAG_CMD
    assert module.RAG_CMD[module.RAG_CMD.index("--port") + 1] == "8001"


def test_port_can_be_overridden_via_env():
    with patch.dict(os.environ, {"RAG_WATCHDOG_PORT": "8004"}):
        module = _load_watchdog_module("rag_watchdog_override_port")
    assert module.RAG_PORT == 8004
    assert module.RAG_CMD[module.RAG_CMD.index("--port") + 1] == "8004"
