"""v2-step-15: 结构化输出 REST 端点。三个业务 schema。"""
from __future__ import annotations
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.structured_output import StructuredOutputClient, outlines_available
from app.core.schemas import TranspileExplanation, SchemaAnalysisResult, MigrationRiskReport

router = APIRouter(tags=["structured"])

# 依赖注入点: main.py override
def _client_dep() -> StructuredOutputClient:
    raise NotImplementedError("main.py 需 dependency_overrides[_client_dep]")


class TranspileExplainReq(BaseModel):
    source_sql: str
    target_sql: str
    source_dialect: str = "mysql"
    target_dialect: str = "opengauss"


class SchemaAnalysisReq(BaseModel):
    schema_summary: str = Field(..., description="DDL / 信息表提取出的文本描述")
    tables_total: Optional[int] = None


class RiskReportReq(BaseModel):
    task_id: int
    context: str = Field(..., description="上下文: 包含表名/SQL/改动点 的多行文本")


class StructuredResp(BaseModel):
    ok: bool
    backend: str
    attempts: int
    elapsed_ms: int
    data: Optional[Dict[str, Any]] = None
    errors: Optional[list] = None


@router.post("/transpile-explain", response_model=StructuredResp)
def transpile_explain(req: TranspileExplainReq, client: StructuredOutputClient = Depends(_client_dep)):
    prompt = (
        f"请对以下 SQL 转译生成中文说明 (JSON):\n\n"
        f"源方言 ({req.source_dialect}):\n{req.source_sql}\n\n"
        f"目标方言 ({req.target_dialect}):\n{req.target_sql}\n\n"
        "请识别函数映射 (如 IFNULL→COALESCE)、分页变化 (LIMIT a,b → LIMIT b OFFSET a)、类型差异, "
        "并评估风险等级与信心度。"
    )
    result = client.generate_json(prompt, TranspileExplanation, max_retries=3)
    return StructuredResp(
        ok=result.ok, backend=result.backend, attempts=result.attempts,
        elapsed_ms=result.elapsed_ms, data=result.data,
        errors=result.errors if result.errors else None,
    )


@router.post("/schema-analysis", response_model=StructuredResp)
def schema_analysis(req: SchemaAnalysisReq, client: StructuredOutputClient = Depends(_client_dep)):
    prompt = (
        "你是资深数据库架构师。请按 JSON Schema 输出对以下表结构的分析:\n\n"
        f"表结构描述:\n{req.schema_summary}\n\n"
        f"{'已知表总数: ' + str(req.tables_total) if req.tables_total else ''}\n\n"
        "请给出: 表总数 / top 5 表 / 关系总数 / 从子表到主表的建议迁移顺序 / 追加备注。"
    )
    fallback = {"tables_total": req.tables_total or 0, "tables_top": [], "relations_total": 0,
                "suggested_migration_order": [], "notes": ["仅从输入描述推断, 未调 LLM"]}
    result = client.generate_json(prompt, SchemaAnalysisResult, max_retries=3, template_fallback=fallback)
    return StructuredResp(
        ok=result.ok, backend=result.backend, attempts=result.attempts,
        elapsed_ms=result.elapsed_ms, data=result.data,
        errors=result.errors if result.errors else None,
    )


@router.post("/risk-report", response_model=StructuredResp)
def risk_report(req: RiskReportReq, client: StructuredOutputClient = Depends(_client_dep)):
    prompt = (
        f"你是数据库迁移风险评估专家。面对 task_id={req.task_id} 的迁移上下文:\n\n"
        f"{req.context}\n\n"
        "请生成风险报告 JSON: 总体风险 (low/medium/high/critical) / 信心度 (0-1) / "
        "各项风险 (分 sql_syntax/data_type/index/performance/security/business 6 类) / "
        "缓解措施 / 总结。"
    )
    fallback = {"task_id": req.task_id, "overall_risk": "low", "confidence": 0.5,
                "risks": [], "recommendations": [], "summary": "默认报告, 请配置 DEEPSEEK_API_KEY 以启用 LLM"}
    result = client.generate_json(prompt, MigrationRiskReport, max_retries=3, template_fallback=fallback)
    return StructuredResp(
        ok=result.ok, backend=result.backend, attempts=result.attempts,
        elapsed_ms=result.elapsed_ms, data=result.data,
        errors=result.errors if result.errors else None,
    )


@router.get("/info")
def info(client: StructuredOutputClient = Depends(_client_dep)):
    """诊断端点: 看到底层走什么后端。"""
    return {
        "backend": client.current_backend(),
        "outlines_available": outlines_available(),
        "outlines_enabled": client.outlines_enabled,
        "deepseek_configured": bool(client.api_key),
        "chat_model": client.chat_model,
    }
