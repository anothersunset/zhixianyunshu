"""v2-step-06: /validation HTTP 入口。生成验证脚本。"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter
from pydantic import BaseModel

from app.pipelines.validation import generate_validation_script, validate_request_payload

router = APIRouter(prefix="/validation", tags=["validation"])


class ValidationRequest(BaseModel):
    task_id: int
    suggestions: List[Dict[str, Any]]
    target_db: str = "openGauss"


class ValidationResponse(BaseModel):
    task_id: int
    scripts: List[Dict[str, Any]]
    errors: List[str] = []


@router.post("/generate", response_model=ValidationResponse)
async def generate(req: ValidationRequest):
    errors = validate_request_payload(req.model_dump())
    if errors:
        return ValidationResponse(task_id=req.task_id, scripts=[], errors=errors)
    scripts = generate_validation_script(req.task_id, req.suggestions, req.target_db)
    return ValidationResponse(task_id=req.task_id, scripts=scripts)
