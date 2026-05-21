"""
v2-step-12: CRAG /crag/query HTTP 入口。
与 /query 并存, /query 保留原有 Self-RAG critic 路径。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter()


class CragReq(BaseModel):
    question: str
    top_k: int = 5
    use_web: bool = True


class CragStepResp(BaseModel):
    node: str
    elapsed_ms: float
    input: dict
    output: dict


class CragResp(BaseModel):
    question: str
    answer: str
    route: str
    confidence: float
    refined_count: int
    docs_count: int
    web_used: bool
    web_count: int
    steps: list[CragStepResp]
    trace_id: Optional[str] = None


# 依赖占位符: main.py 会用 dependency_overrides 注入 CragRunner 实例
def _runner_dep():
    raise NotImplementedError("CragRunner 未注入, 请在 main.py 里设 app.dependency_overrides[_runner_dep] = lambda: ...")


@router.post("/query", response_model=CragResp)
def crag_query(req: CragReq, runner = Depends(_runner_dep)):
    state = runner.run(req.question, top_k=req.top_k, use_web=req.use_web)
    return CragResp(
        question=req.question,
        answer=state.get("answer") or "",
        route=state.get("route") or "",
        confidence=state.get("confidence") or 0.0,
        refined_count=len(state.get("refined") or []),
        docs_count=len(state.get("docs") or []),
        web_used=bool(state.get("web_docs")),
        web_count=len(state.get("web_docs") or []),
        steps=[CragStepResp(**s) for s in state.get("steps") or []],
        trace_id=state.get("trace_id"),
    )
