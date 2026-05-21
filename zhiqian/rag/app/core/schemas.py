"""v2-step-15: 业务 schema (pydantic v2)。

三个场景都是 LLM 输出结构化的核心生产点:
  1. TranspileExplanation: SQL 转译说明 (插拔 #9 sqlglot 之上)
  2. SchemaAnalysisResult: CKG 表结构分析 (#3 SchemaAnalyzerAgent 结果结构化)
  3. MigrationRiskReport: 迁移风险评估 (#3 SqlCriticAgent + ReportSummarizerAgent 汇总)

主动设计为 pydantic v2, 方便 model_json_schema() 拼 prompt + outlines 送 schema。
"""
from __future__ import annotations
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, conlist


class FunctionMapping(BaseModel):
    source: str = Field(..., description="源方言函数名, 例: IFNULL")
    target: str = Field(..., description="目标方言函数名, 例: COALESCE")
    reason: str = Field(..., description="为什么需要这个映射 (中文一句话)")


class TranspileExplanation(BaseModel):
    """#9 sqlglot 输出后, 调 LLM 生成可解释的转译说明。"""
    function_mappings: List[FunctionMapping] = Field(default_factory=list)
    pagination_change: Optional[str] = Field(None, description="如有 LIMIT/OFFSET 调整, 描述。无则 null")
    type_change: Optional[str] = Field(None, description="如有类型变动描述。无则 null")
    risk_level: Literal["low", "medium", "high"] = Field("low", description="转译质量风险等级")
    confidence: float = Field(..., ge=0.0, le=1.0, description="转译信心度 0-1")
    notes: List[str] = Field(default_factory=list, description="追加备注 (例: 虚拟不同, 需人工复检)")


class TableInfo(BaseModel):
    name: str
    columns_count: int = Field(..., ge=0)
    has_primary_key: bool = False
    estimated_rows: Optional[int] = Field(None, ge=0)
    tags: List[str] = Field(default_factory=list, description="例: hot, archive, fact, dim")


class SchemaAnalysisResult(BaseModel):
    """#3 SchemaAnalyzerAgent 输出结构化。"""
    tables_total: int = Field(..., ge=0)
    tables_top: List[TableInfo] = Field(default_factory=list, description="top 5 表")
    relations_total: int = Field(0, ge=0)
    suggested_migration_order: List[str] = Field(default_factory=list, description="从子表到主表的建议迁移顺序")
    notes: List[str] = Field(default_factory=list)


class RiskItem(BaseModel):
    category: Literal["sql_syntax", "data_type", "index", "performance", "security", "business"] 
    severity: Literal["low", "medium", "high", "critical"]
    description: str
    mitigation: Optional[str] = None


class MigrationRiskReport(BaseModel):
    """#3 SqlCritic + ReportSummarizer 联合输出。"""
    task_id: int
    overall_risk: Literal["low", "medium", "high", "critical"]
    confidence: float = Field(..., ge=0.0, le=1.0)
    risks: List[RiskItem] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    summary: str


def export_schema(model_cls) -> dict:
    """输出 JSON Schema (pydantic v2 model_json_schema)。拼 prompt + outlines 送 schema 都走这个。"""
    return model_cls.model_json_schema()
