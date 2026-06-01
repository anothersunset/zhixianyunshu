"""v2-step-09: SQL 方言 AST 转译 API。

- POST /transpile        — 单句 SQL, 默认 explain=true 返回中文变动说明
- POST /transpile/batch  — 批量, 逐条 ok=true/false + summary

两端点都被 Langfuse 包在 trace 里 (rag.transpile / rag.transpile.batch)。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.observability import get_langfuse
from app.core.sql_transpiler import (
    explain_transpile,
    transpile_batch,
    transpile_one,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/transpile", tags=["transpile"])


class TranspileReq(BaseModel):
    sql: str
    source: str = "mysql"
    target: str = "postgres"  # opengauss/gauss/pg/postgresql 都会 alias 到 postgres
    explain: bool = True
    pretty: bool = True


class TranspileResp(BaseModel):
    ok: bool
    source: str
    target: Optional[str] = None
    source_dialect: Optional[str] = None
    target_dialect: Optional[str] = None
    notes: Optional[List[Dict[str, str]]] = None
    sqlglot_version: Optional[str] = None
    error: Optional[str] = None


@router.post("", response_model=TranspileResp)
async def transpile(req: TranspileReq) -> TranspileResp:
    lf = get_langfuse()
    with lf.trace(
        "rag.transpile",
        input={
            "source_dialect": req.source,
            "target_dialect": req.target,
            "sql_len": len(req.sql or ""),
            "explain": req.explain,
        },
        tags=["transpile"],
    ) as tr:
        if req.explain:
            result = explain_transpile(req.sql, req.source, req.target)
        else:
            try:
                t = transpile_one(req.sql, req.source, req.target, pretty=req.pretty)
                result = {
                    "ok": True,
                    "source": req.sql,
                    "target": t,
                    "source_dialect": req.source,
                    "target_dialect": req.target,
                }
            except Exception as e:  # noqa: BLE001
                result = {"ok": False, "source": req.sql, "error": str(e)}
        tr.output({
            "ok": result.get("ok"),
            "target_len": len(result.get("target") or "") if result.get("ok") else 0,
            "notes": len(result.get("notes") or []),
        })
    return TranspileResp(**{k: result.get(k) for k in TranspileResp.model_fields.keys() if k in result})


class TranspileBatchReq(BaseModel):
    sqls: List[str]
    source: str = "mysql"
    target: str = "postgres"


class TranspileBatchResp(BaseModel):
    items: List[Dict[str, Any]]
    summary: Dict[str, int]


@router.post("/batch", response_model=TranspileBatchResp)
async def transpile_batch_api(req: TranspileBatchReq) -> TranspileBatchResp:
    lf = get_langfuse()
    with lf.trace(
        "rag.transpile.batch",
        input={
            "count": len(req.sqls),
            "source_dialect": req.source,
            "target_dialect": req.target,
        },
        tags=["transpile", "batch"],
    ) as tr:
        items = transpile_batch(req.sqls, req.source, req.target)
        ok_count = sum(1 for x in items if x.get("ok"))
        summary = {"total": len(items), "ok": ok_count, "fail": len(items) - ok_count}
        tr.output(summary)
    return TranspileBatchResp(items=items, summary=summary)
