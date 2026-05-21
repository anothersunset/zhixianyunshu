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
    """无 DEEPSEEK_API_KEY 时, 走 pydantic_only 返默认值。"""
    with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "", "RAG_OUTLINES_ENABLED": "false"}, clear=False):
        client = StructuredOutputClient()
        assert client.current_backend() == "pydantic_only"
        r = client.generate_json("任意 prompt", TranspileExplanation, max_retries=1)
        assert r.ok is True
        assert r.backend == "pydantic_only"
        assert r.data is not None
        assert r.data["confidence"] == 0.5
        assert r.data["risk_level"] == "low"


def test_outlines_optional_import_no_crash():
    """不装 outlines 也能跑, outlines_available() 返 False 但不报错。"""
    assert isinstance(outlines_available(), bool)


def test_backend_selection_with_key():
    """有 key + 无 outlines 选择 deepseek_json_mode。"""
    with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test", "RAG_OUTLINES_ENABLED": "false"}, clear=False):
        client = StructuredOutputClient()
        assert client.current_backend() == "deepseek_json_mode"


def test_template_fallback_risk_report_min_fields():
    """MigrationRiskReport 默认 fallback 能被 pydantic 验证。"""
    with patch.dict(os.environ, {"DEEPSEEK_API_KEY": ""}, clear=False):
        client = StructuredOutputClient()
        r = client.generate_json("x", MigrationRiskReport, max_retries=1)
        assert r.ok is True
        assert r.data["overall_risk"] in ("low", "medium", "high", "critical")
        assert 0.0 <= r.data["confidence"] <= 1.0
