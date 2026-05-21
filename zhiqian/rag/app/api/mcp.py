"""v2-step-23: MCP HTTP 路由。JSON-RPC 2.0 + manifest endpoint。"""
from __future__ import annotations
import uuid
from typing import Any, Dict

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.mcp.server import build_manifest, dispatch, TOOLS

router = APIRouter(prefix="/mcp", tags=["mcp"])


@router.get("/manifest")
async def manifest() -> Dict[str, Any]:
    return build_manifest()


@router.get("/tools")
async def tools_list() -> Dict[str, Any]:
    """便捷非标准端点。标准 MCP 客户端用 /mcp/rpc + tools/list。"""
    return {"tools": TOOLS}


@router.post("/rpc")
async def jsonrpc(request: Request) -> JSONResponse:
    body = await request.json()
    rpc_id = body.get("id", str(uuid.uuid4()))
    method = body.get("method")
    params = body.get("params", {}) or {}
    try:
        result = await dispatch(method, params, request.app.state)
        return JSONResponse({"jsonrpc": "2.0", "id": rpc_id, "result": result})
    except ValueError as e:
        return JSONResponse({
            "jsonrpc": "2.0", "id": rpc_id,
            "error": {"code": -32601, "message": str(e)}
        }, status_code=400)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({
            "jsonrpc": "2.0", "id": rpc_id,
            "error": {"code": -32603, "message": f"Internal: {e}"}
        }, status_code=500)


# Claude Desktop 克难接口: /mcp/call 是 /mcp/rpc 的别名 (tools/call 类比)
@router.post("/call")
async def mcp_call(request: Request) -> JSONResponse:
    body = await request.json()
    name = body.get("name")
    args = body.get("arguments", {})
    rpc_id = body.get("id", str(uuid.uuid4()))
    try:
        result = await dispatch("tools/call", {"name": name, "arguments": args}, request.app.state)
        return JSONResponse({"jsonrpc": "2.0", "id": rpc_id, "result": result})
    except Exception as e:  # noqa: BLE001
        return JSONResponse({
            "jsonrpc": "2.0", "id": rpc_id,
            "error": {"code": -32603, "message": str(e)}
        }, status_code=500)
