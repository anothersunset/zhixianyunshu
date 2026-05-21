"""v2-step-23: MCP 测试。mock httpx 避免起全 stack。"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from app.main import app
from app.mcp.server import TOOLS

client = TestClient(app)


def test_mcp_manifest():
    r = client.get("/mcp/manifest")
    assert r.status_code == 200
    d = r.json()
    assert d["serverInfo"]["name"] == "zhiqian-mcp"
    assert d["capabilities"]["tools"]["listChanged"] is False
    assert d["protocolVersion"]


def test_mcp_tools_list():
    r = client.get("/mcp/tools")
    assert r.status_code == 200
    tools = r.json()["tools"]
    assert len(tools) == 6
    names = {t["name"] for t in tools}
    assert {"sql_transpile","sql_explain","schema_analysis","risk_report","retrieve","migrate_query"} == names


def test_mcp_jsonrpc_initialize():
    r = client.post("/mcp/rpc", json={"jsonrpc":"2.0","id":"1","method":"initialize"})
    assert r.status_code == 200
    assert r.json()["result"]["serverInfo"]["name"] == "zhiqian-mcp"


def test_mcp_jsonrpc_tools_list():
    r = client.post("/mcp/rpc", json={"jsonrpc":"2.0","id":"2","method":"tools/list"})
    assert r.status_code == 200
    assert len(r.json()["result"]["tools"]) == 6


def test_mcp_jsonrpc_unknown_method():
    r = client.post("/mcp/rpc", json={"jsonrpc":"2.0","id":"3","method":"bogus/method"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == -32601


@patch("app.mcp.server.httpx")
def test_mcp_tools_call_transpile(httpx_mod):
    fake_response = type("R", (), {"raise_for_status": lambda self: None,
                                    "json": lambda self: {"target_sql": "SELECT COALESCE(a,b) FROM t LIMIT 10"}})()
    async_client = AsyncMock()
    async_client.__aenter__.return_value = async_client
    async_client.__aexit__.return_value = None
    async_client.post = AsyncMock(return_value=fake_response)
    httpx_mod.AsyncClient = lambda *a, **kw: async_client

    r = client.post("/mcp/rpc", json={
        "jsonrpc":"2.0","id":"4","method":"tools/call",
        "params":{"name":"sql_transpile","arguments":{"source_sql":"SELECT IFNULL(a,b) FROM t LIMIT 5,10"}}
    })
    assert r.status_code == 200
    res = r.json()["result"]
    assert res["isError"] is False
    assert "target_sql" in res["content"][0]["text"]
