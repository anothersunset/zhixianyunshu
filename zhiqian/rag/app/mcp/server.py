"""v2-step-23: MCP (Model Context Protocol) server.

暴露 ZhiQian 的转译 / 说明 / 检索 能力给外部 AI (Claude Desktop, ChatGPT custom GPT, Cursor)。
JSON-RPC 2.0 over HTTP。实现依 MCP spec 0.4 最小集: tools/list + tools/call + initialize。
实际生产环境应走 stdio transport 可被 Claude Desktop 主动拉起,
但 SSE/HTTP transport 更适合服务化部署。
"""
from __future__ import annotations
import json
import logging
import os
import time
from typing import Any, Dict, List

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

SERVER_NAME = "zhiqian-mcp"
SERVER_VERSION = "2.0.0"
PROTOCOL_VERSION = "2024-11-05"

# 工具清单。schema 走 JSON Schema draft-07。
TOOLS: List[Dict[str, Any]] = [
    {
        "name": "sql_transpile",
        "description": "将 SQL 从源方言转译到目标方言, 返转译后 SQL + AST 差异。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_sql": {"type": "string", "minLength": 1, "description": "原始 SQL"},
                "source_dialect": {"type": "string", "enum": ["mysql","oracle","postgres","sqlserver","db2"], "default": "mysql"},
                "target_dialect": {"type": "string", "enum": ["opengauss","postgres","mysql"], "default": "opengauss"}
            },
            "required": ["source_sql"]
        }
    },
    {
        "name": "sql_explain",
        "description": "结构化解释 SQL 转译变动 (添加/删除/修改 + 风险等级 + 置信度)。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_sql": {"type": "string", "minLength": 1},
                "source_dialect": {"type": "string", "default": "mysql"},
                "target_dialect": {"type": "string", "default": "opengauss"},
                "target_sql": {"type": "string", "minLength": 1}
            },
            "required": ["source_sql"]
        }
    },
    {
        "name": "schema_analysis",
        "description": "分析 DDL 表结构, 返 columns + indexes + constraints + 迁移风险评价。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "schema_summary": {"type": "string", "minLength": 1},
                "tables_total": {"type": "integer", "minimum": 0}
            },
            "required": ["schema_summary"]
        }
    },
    {
        "name": "risk_report",
        "description": "为一组 SQL/DDL 迁移生成风险报告 (分级、商业影响、建议)。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer"},
                "context": {"type": "string", "minLength": 1}
            },
            "required": ["task_id", "context"]
        }
    },
    {
        "name": "retrieve",
        "description": "从 ZhiQian RAG 检索迁移知识 (BGE-M3 + RRF 三路混合)。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1},
                "top_k": {"type": "integer", "default": 8, "minimum": 1, "maximum": 50}
            },
            "required": ["query"]
        }
    },
    {
        "name": "migrate_query",
        "description": "CRAG 增强问答: 检索 + 评估 + 补救 + 生成, 适合 'X 该怎么迁移' 这种问题。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "minLength": 1},
                "top_k": {"type": "integer", "default": 5, "minimum": 1, "maximum": 50},
                "use_web": {"type": "boolean", "default": True}
            },
            "required": ["question"]
        }
    }
]


def build_manifest() -> Dict[str, Any]:
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        "instructions": (
            "ZhiQian YunShu 是智能数据库迁移平台。调用者可用上面 6 个工具完成 SQL 转译、"
            "schema 分析、风险报告、迁移知识检索。默认目标方言是 openGauss。"
        )
    }


async def dispatch(method: str, params: Dict[str, Any], deps) -> Any:
    """分发 JSON-RPC 方法到现有 RAG 代码。deps 是 FastAPI app.state 依赖集。"""
    if method == "initialize":
        return build_manifest()
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {}) or {}
        return await _call_tool(name, args, deps)
    raise ValueError(f"unknown method: {method}")


def _validated_request(
    model_cls: type[BaseModel], payload: Dict[str, Any]
) -> Dict[str, Any]:
    """Validate internal HTTP payloads against the endpoint's real schema."""
    return model_cls.model_validate(payload).model_dump(
        exclude_none=True,
        exclude_unset=True,
    )


async def _call_tool(name: str, args: Dict[str, Any], deps) -> Dict[str, Any]:
    """调现有服务。远端调用 (各 endpoint 独立 httpx) 是为了避免循环 import。"""
    base = os.getenv("MCP_INTERNAL_BASE_URL", "http://localhost:8001")
    started = time.time()
    try:
        # Local imports avoid an import cycle while keeping MCP-to-HTTP
        # contracts tied to the exact FastAPI Pydantic request models.
        from app.api.crag import CragReq
        from app.api.retrieve import RetrieveReq
        from app.api.structured import (
            RiskReportReq,
            SchemaAnalysisReq,
            TranspileExplainReq,
        )
        from app.api.transpile import TranspileReq

        async with httpx.AsyncClient(base_url=base, timeout=120) as client:
            if name == "sql_transpile":
                body = _validated_request(TranspileReq, {
                    "sql": args.get("source_sql"),
                    "source": args.get("source_dialect", "mysql"),
                    "target": args.get("target_dialect", "opengauss")
                })
                r = await client.post("/transpile", json=body)
            elif name == "sql_explain":
                target_sql = args.get("target_sql")
                if not target_sql:
                    transpile_body = _validated_request(TranspileReq, {
                        "sql": args.get("source_sql"),
                        "source": args.get("source_dialect", "mysql"),
                        "target": args.get("target_dialect", "opengauss")
                    })
                    transpiled = await client.post("/transpile", json=transpile_body)
                    transpiled.raise_for_status()
                    target_sql = transpiled.json().get("target")
                body = _validated_request(TranspileExplainReq, {
                    "source_sql": args.get("source_sql"),
                    "target_sql": target_sql,
                    "source_dialect": args.get("source_dialect", "mysql"),
                    "target_dialect": args.get("target_dialect", "opengauss")
                })
                r = await client.post("/structured/transpile-explain", json=body)
            elif name == "schema_analysis":
                body = _validated_request(SchemaAnalysisReq, {
                    "schema_summary": args.get("schema_summary", args.get("ddl")),
                    "tables_total": args.get("tables_total")
                })
                r = await client.post("/structured/schema-analysis", json=body)
            elif name == "risk_report":
                body = _validated_request(RiskReportReq, {
                    "task_id": args.get("task_id"),
                    "context": args.get("context")
                })
                r = await client.post("/structured/risk-report", json=body)
            elif name == "retrieve":
                body = _validated_request(RetrieveReq, {
                    "query": args.get("query"),
                    "top_k": args.get("top_k", args.get("k", 8))
                })
                r = await client.post("/retrieve", json=body)
            elif name == "migrate_query":
                body = _validated_request(CragReq, {
                    "question": args.get("question"),
                    "top_k": args.get("top_k", 5),
                    "use_web": args.get("use_web", True)
                })
                r = await client.post("/crag/query", json=body)
            else:
                return _error_content(f"unknown tool: {name}")
            r.raise_for_status()
            payload = r.json()
    except Exception as e:  # noqa: BLE001
        logger.exception("mcp tool error")
        return _error_content(str(e))

    elapsed = round(time.time() - started, 3)
    return {
        "content": [
            {"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}
        ],
        "isError": False,
        "_zhiqian_meta": {"tool": name, "elapsed_seconds": elapsed}
    }


def _error_content(msg: str) -> Dict[str, Any]:
    return {
        "content": [{"type": "text", "text": f"ERROR: {msg}"}],
        "isError": True
    }
