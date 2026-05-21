"""v2-step-27: PDF 报告 endpoint。"""
from __future__ import annotations
import io
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from app.reports.typst_renderer import render_pdf, typst_available

router = APIRouter(prefix="/reports", tags=["reports"])


class ReportStats(BaseModel):
    total_sql: int = 0
    success: int = 0
    manual: int = 0
    high_risk: int = 0
    tables: int = 0
    indexes_changed: int = 0


class ReportRisk(BaseModel):
    kind: str
    description: str
    level: str = "中"
    suggestion: str = ""


class ReportExample(BaseModel):
    title: str
    source: str
    target: str
    explanation: str = ""


class ReportRequest(BaseModel):
    project_name: str
    source_dialect: str = "mysql"
    target_dialect: str = "opengauss"
    generated_at: str = ""
    owner: str = "ZhiQian"
    summary: str = ""
    stats: ReportStats = Field(default_factory=ReportStats)
    risks: List[ReportRisk] = []
    examples: List[ReportExample] = []


@router.get("/status")
async def status():
    return {"typst_available": typst_available()}


@router.post("/generate")
async def generate_pdf(req: ReportRequest):
    if not typst_available():
        return JSONResponse({"error": "typst CLI not installed. brew install typst / cargo install typst-cli"},
                            status_code=503)
    data: Dict[str, Any] = req.model_dump()
    pdf_bytes = render_pdf("migration-report", data)
    if pdf_bytes is None:
        return JSONResponse({"error": "typst compile failed"}, status_code=500)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="migration-report-{req.project_name}.pdf"'},
    )


@router.post("/preview")
async def preview(req: ReportRequest):
    """不调 typst, 返 data 结构供前端预览。"""
    return {"data": req.model_dump(), "typst_available": typst_available()}
