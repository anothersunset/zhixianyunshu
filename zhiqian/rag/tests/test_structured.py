"""v2-step-15: 结构化输出测试。不依赖 LLM 联网。"""
import os
import pytest
from unittest.mock import patch
from app.core.schemas import (
    TranspileExplanation, SchemaAnalysisResult, MigrationRiskReport,
    export_schema,
)
from app.core.structured_output import StructuredOutputClient, outlines_available


def test_schema_export():
    """3 个业务 schema 都能导出 JSON Schema。"""
    for cls in [TranspileExplanation, SchemaAnalysisResult, MigrationRiskReport]:
        s = export_schema(cls)
        assert s["type"] == "object"
        assert "properties" in s


def test_transpile_explanation_pydantic():
    obj = TranspileExplanation(
        function_mappings=[],
        pagination_change="LIMIT a,b → LIMIT b OFFSET a",
        risk_level="low",
        confidence=0.9,
    )
    assert obj.confidence == 0.9
    assert obj.risk_level == "low"
    with pytest.raises(Exception):
        TranspileExplanation(confidence=2.0)  # 越界


def test_fallback_template_when_no_key():
    """无 DEEPSEEK_API_KEY 时走 pydantic_only 模板降级: ok=False 显式降级, 不谎报质量判断。"""
    with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "", "RAG_OUTLINES_ENABLED": "false"}, clear=False):
        client = StructuredOutputClient()
        assert client.current_backend() == "pydantic_only"
        r = client.generate_json("任意 prompt", TranspileExplanation, max_retries=1)
        assert r.ok is False, "模板降级不得声称 ok=True"
        assert r.backend == "pydantic_only"
        assert r.data is not None, "降级仍应携带模板数据供消费方使用"
        assert r.data["confidence"] == 0.0, "降级产物不得伪造信心度"
        assert r.data["risk_level"] == "unknown", "降级产物不得谎报 low 风险"
        assert r.errors, "降级原因必须写进 errors"


def test_outlines_optional_import_no_crash():
    """不装 outlines 也能跑, outlines_available() 返 False 但不报错。"""
    assert isinstance(outlines_available(), bool)


def test_backend_selection_with_key():
    """有 key + 无 outlines 选择 deepseek_json_mode。"""
    with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test", "RAG_OUTLINES_ENABLED": "false"}, clear=False):
        client = StructuredOutputClient()
        assert client.current_backend() == "deepseek_json_mode"


def test_template_fallback_risk_report_min_fields():
    """MigrationRiskReport 模板降级: overall_risk 恒为 unknown, ok=False。"""
    with patch.dict(os.environ, {"DEEPSEEK_API_KEY": ""}, clear=False):
        client = StructuredOutputClient()
        r = client.generate_json("x", MigrationRiskReport, max_retries=1)
        assert r.ok is False
        assert r.backend == "pydantic_only"
        assert r.data["overall_risk"] == "unknown"
        assert r.data["confidence"] == 0.0
        assert any("degraded" in e for e in r.errors)


def test_endpoint_risk_report_degraded_response(client):
    """/structured/risk-report 无 LLM key 时: 200 + ok=False + overall_risk=unknown。"""
    from app.api import structured as structured_api
    from app.core.structured_output import StructuredOutputClient

    monkeypatched = StructuredOutputClient.__new__(StructuredOutputClient)
    monkeypatched.api_key = ""
    monkeypatched.base_url = "https://api.deepseek.com/v1"
    monkeypatched.chat_model = "deepseek-chat"
    monkeypatched.outlines_enabled = False
    monkeypatched.timeout = 1.0

    original = client.app.dependency_overrides.get(structured_api._client_dep)
    client.app.dependency_overrides[structured_api._client_dep] = lambda: monkeypatched
    try:
        resp = client.post(
            "/structured/risk-report",
            json={"task_id": 42, "context": "CREATE TABLE t (id INT)"},
        )
    finally:
        if original is None:
            client.app.dependency_overrides.pop(structured_api._client_dep, None)
        else:
            client.app.dependency_overrides[structured_api._client_dep] = original

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["backend"] == "pydantic_only"
    assert body["data"]["overall_risk"] == "unknown"
    assert body["data"]["task_id"] == 42
    assert body["errors"]
