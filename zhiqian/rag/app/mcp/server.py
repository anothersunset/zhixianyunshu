"""v2-step-23: MCP (Model Context Protocol) server.

暴露 ZhiQian 的转译 / 说明 / 检索 能力给外部 AI (Claude Desktop, ChatGPT custom GPT, Cursor)。
JSON-RPC 2.0 over HTTP。实现依 MCP spec 0.4 最小集: tools/list + tools/call + initialize。
实际生产环境应走 stdio transport 可被 Claude Desktop 主动拉起,
但 SSE/HTTP transport 更适合服务化部署。
"""
from __future__ import annotations
import json
import logging
import time
from typing import Any, Dict, List

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
                "source_sql": {"type": "string", "description": "原始 SQL"},
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
                "source_sql": {"type": "string"},
                "source_dialect": {"type": "string", "default": "mysql"},
                "target_dialect": {"type": "string", "default": "opengauss"}
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
                "ddl": {"type": "string"},
                "dialect": {"type": "string", "default": "mysql"}
            },
            "required": ["ddl"]
        }
    },
    {
        "name": "risk_report",
        "description": "为一组 SQL/DDL 迁移生成风险报告 (分级、商业影响、建议)。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sql_list": {"type": "array", "items": {"type": "string"}},
                "source_dialect": {"type": "string", "default": "mysql"},
                "target_dialect": {"type": "string", "default": "opengauss"}
            },
            "required": ["sql_list"]
        }
    },
    {
        "name": "retrieve",
        "description": "从 ZhiQian RAG 检索迁移知识 (BGE-M3 + RRF 三路混合)。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "k": {"type": "integer", "default": 8, "minimum": 1, "maximum": 50}
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
                "question": {"type": "string"},
                "context": {"type": "string", "description": "可选上下文"}
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


async def _call_tool(name: str, args: Dict[str, Any], deps) -> Dict[str, Any]:
    """调现有服务。远端调用 (各 endpoint 独立 httpx) 是为了避免循环 import。"""
    import httpx
    base = "http://localhost:8001"
    started = time.time()
    try:
        async with httpx.AsyncClient(base_url=base, timeout=120) as client:
            if name == "sql_transpile":
                r = await client.post("/transpile", json={
                    "source_sql": args.get("source_sql"),
                    "source_dialect": args.get("source_dialect", "mysql"),
                    "target_dialect": args.get("target_dialect", "opengauss")
                })
            elif name == "sql_explain":
                r = await client.post("/structured/transpile-explain", json={
                    "source_sql": args.get("source_sql"),
                    "source_dialect": args.get("source_dialect", "mysql"),
                    "target_dialect": args.get("target_dialect", "opengauss")
                })
            elif name == "schema_analysis":
                r = await client.post("/structured/schema-analysis", json={
                    "ddl": args.get("ddl"),
                    "dialect": args.get("dialect", "mysql")
                })
            elif name == "risk_report":
                r = await client.post("/structured/risk-report", json={
                    "sql_list": args.get("sql_list", []),
                    "source_dialect": args.get("source_dialect", "mysql"),
                    "target_dialect": args.get("target_dialect", "opengauss")
                })
            elif name == "retrieve":
                r = await client.post("/retrieve", json={"query": args.get("query"), "k": args.get("k", 8)})
            elif name == "migrate_query":
                r = await client.post("/crag/query", json={
                    "query": args.get("question"),
                    "context": args.get("context")
                })
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
