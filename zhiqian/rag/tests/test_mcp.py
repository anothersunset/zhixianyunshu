"""v2-step-23: MCP 测试。mock httpx 避免起全 stack。"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, call, patch

from app.main import app
from app.api import crag, retrieve as retrieve_api, structured
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
    source_sql = """SELECT
  IFNULL(name, 'n/a') AS display_name
FROM users
WHERE note = 'quoted "value"';"""
    fake_response = type("R", (), {"raise_for_status": lambda self: None,
                                    "json": lambda self: {"target": "SELECT COALESCE(name, 'n/a') FROM users"}})()
    async_client = AsyncMock()
    async_client.__aenter__.return_value = async_client
    async_client.__aexit__.return_value = None
    async_client.post = AsyncMock(return_value=fake_response)
    httpx_mod.AsyncClient = lambda *a, **kw: async_client

    r = client.post("/mcp/rpc", json={
        "jsonrpc":"2.0","id":"4","method":"tools/call",
        "params":{"name":"sql_transpile","arguments":{"source_sql": source_sql}}
    })
    assert r.status_code == 200
    res = r.json()["result"]
    assert res["isError"] is False
    assert '"target"' in res["content"][0]["text"]
    async_client.post.assert_awaited_once_with("/transpile", json={
        "sql": source_sql,
        "source": "mysql",
        "target": "opengauss",
    })


@pytest.mark.parametrize(
    ("name", "arguments", "expected_path", "expected_body"),
    [
        (
            "schema_analysis",
            {"schema_summary": "CREATE TABLE users (id INT);", "tables_total": 1},
            "/structured/schema-analysis",
            {"schema_summary": "CREATE TABLE users (id INT);", "tables_total": 1},
        ),
        (
            "risk_report",
            {"task_id": 42, "context": "SQL:\nSELECT 1;\nRisk: review required"},
            "/structured/risk-report",
            {"task_id": 42, "context": "SQL:\nSELECT 1;\nRisk: review required"},
        ),
        (
            "retrieve",
            {"query": "IFNULL migration", "top_k": 3},
            "/retrieve",
            {"query": "IFNULL migration", "top_k": 3},
        ),
        (
            "migrate_query",
            {"question": "How should IFNULL migrate?", "top_k": 2, "use_web": False},
            "/crag/query",
            {"question": "How should IFNULL migrate?", "top_k": 2, "use_web": False},
        ),
    ],
)
@patch("app.mcp.server.httpx")
def test_mcp_tool_payloads_match_fastapi_schemas(
    httpx_mod, name, arguments, expected_path, expected_body
):
    fake_response = type(
        "R",
        (),
        {"raise_for_status": lambda self: None, "json": lambda self: {"ok": True}},
    )()
    async_client = AsyncMock()
    async_client.__aenter__.return_value = async_client
    async_client.__aexit__.return_value = None
    async_client.post = AsyncMock(return_value=fake_response)
    httpx_mod.AsyncClient = lambda *a, **kw: async_client

    response = client.post(
        "/mcp/rpc",
        json={
            "jsonrpc": "2.0",
            "id": name,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
    )

    assert response.status_code == 200
    assert response.json()["result"]["isError"] is False
    async_client.post.assert_awaited_once_with(expected_path, json=expected_body)


@patch("app.mcp.server.httpx")
def test_mcp_sql_explain_transpiles_before_structured_call(httpx_mod):
    source_sql = "SELECT\n  IFNULL(total, 0)\nFROM invoices;"
    target_sql = "SELECT\n  COALESCE(total, 0)\nFROM invoices;"
    transpile_response = type(
        "R",
        (),
        {"raise_for_status": lambda self: None, "json": lambda self: {"target": target_sql}},
    )()
    explain_response = type(
        "R",
        (),
        {"raise_for_status": lambda self: None, "json": lambda self: {"ok": True}},
    )()
    async_client = AsyncMock()
    async_client.__aenter__.return_value = async_client
    async_client.__aexit__.return_value = None
    async_client.post = AsyncMock(side_effect=[transpile_response, explain_response])
    httpx_mod.AsyncClient = lambda *a, **kw: async_client

    response = client.post(
        "/mcp/rpc",
        json={
            "jsonrpc": "2.0",
            "id": "explain",
            "method": "tools/call",
            "params": {
                "name": "sql_explain",
                "arguments": {"source_sql": source_sql},
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["result"]["isError"] is False
    assert async_client.post.await_args_list == [
        call(
            "/transpile",
            json={"sql": source_sql, "source": "mysql", "target": "opengauss"},
        ),
        call(
            "/structured/transpile-explain",
            json={
                "source_sql": source_sql,
                "target_sql": target_sql,
                "source_dialect": "mysql",
                "target_dialect": "opengauss",
            },
        ),
    ]


def test_p0_routes_with_lifespan_and_real_request_models(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    monkeypatch.setenv("RAG_OUTLINES_ENABLED", "false")
    source_sql = """SELECT
  IFNULL(name, 'n/a') AS display_name
FROM users
WHERE active = 1;"""

    class CaptureRetriever:
        top_k = None

        def search(self, query, *, top_k, trace_out, **kwargs):
            self.top_k = top_k
            trace_out.update({"mode": kwargs["mode"], "result_ids": ["doc-1"]})
            return [{
                "id": "doc-1",
                "text": "IFNULL maps to COALESCE",
                "score": 1.0,
                "source": "test",
            }]

        def capabilities(self, collection):
            return {"collection": collection, "bm25": True}

    with TestClient(app) as live_client:
        assert crag._runner_dep in app.dependency_overrides
        assert structured._client_dep in app.dependency_overrides

        transpiled = live_client.post(
            "/transpile",
            json={"sql": source_sql, "source": "mysql", "target": "opengauss"},
        )
        assert transpiled.status_code == 200
        assert transpiled.json()["source"] == source_sql
        target_sql = transpiled.json()["target"]

        explained = live_client.post(
            "/structured/transpile-explain",
            json={
                "source_sql": source_sql,
                "target_sql": target_sql,
                "source_dialect": "mysql",
                "target_dialect": "opengauss",
            },
        )
        assert explained.status_code == 200

        schema = live_client.post(
            "/structured/schema-analysis",
            json={"schema_summary": "CREATE TABLE users (id INT);", "tables_total": 1},
        )
        assert schema.status_code == 200

        risk = live_client.post(
            "/structured/risk-report",
            json={"task_id": 42, "context": f"Source SQL:\n{source_sql}"},
        )
        assert risk.status_code == 200

        crag_response = live_client.post(
            "/crag/query",
            json={"question": "How should IFNULL migrate?", "top_k": 1, "use_web": False},
        )
        assert crag_response.status_code == 200

        captured = CaptureRetriever()
        original_retriever = app.dependency_overrides[retrieve_api._retriever]
        app.dependency_overrides[retrieve_api._retriever] = lambda: captured
        try:
            retrieved = live_client.post(
                "/retrieve", json={"query": "IFNULL migration", "top_k": 7}
            )
        finally:
            app.dependency_overrides[retrieve_api._retriever] = original_retriever
        assert retrieved.status_code == 200
        assert captured.top_k == 7
