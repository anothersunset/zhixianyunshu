from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from app.pipelines.retriever import HybridRetriever
from app.pipelines.critic import SelfRagCritic
from app.pipelines.rewriter import QueryRewriter
from app.pipelines.validation import generate_validation_script, validate_request_payload
from app.config import settings

app = FastAPI(
    title="ZhiQian RAG Service",
    description="智迁云枢 RAG 服务：BM25 + 嵌入检索、Self-RAG critic、验证脚本生成",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局单例组件
retriever = HybridRetriever()
critic = SelfRagCritic()
rewriter = QueryRewriter()


class QueryReq(BaseModel):
    question: str
    top_k: int = 5
    rewrite: bool = True
    critic: bool = True
    filters: Optional[Dict[str, Any]] = None


class DocChunk(BaseModel):
    id: str
    text: str
    score: float
    source: str
    meta: Optional[Dict[str, Any]] = None


class QueryResp(BaseModel):
    question: str
    rewritten: Optional[str] = None
    chunks: List[DocChunk]
    critique: Optional[Dict[str, Any]] = None


@app.get("/health")
def health():
    return {"status": "ok", "service": "zhiqian-rag", "version": app.version}


@app.post("/query", response_model=QueryResp)
def query(req: QueryReq):
    q = req.question
    rewritten = rewriter.rewrite(q) if req.rewrite else None
    chunks_raw = retriever.search(rewritten or q, top_k=req.top_k, filters=req.filters)
    critique = critic.critique(q, chunks_raw) if req.critic else None
    return QueryResp(
        question=q,
        rewritten=rewritten,
        chunks=[DocChunk(**c) for c in chunks_raw],
        critique=critique,
    )


class ValidationReq(BaseModel):
    task_id: int
    suggestions: List[Dict[str, Any]]
    target_db: str = "openGauss"


@app.post("/validation/generate")
def validation_generate(req: ValidationReq):
    errors = validate_request_payload(req.dict())
    if errors:
        return {"ok": False, "errors": errors}
    scripts = generate_validation_script(
        task_id=req.task_id,
        suggestions=req.suggestions,
        target_db=req.target_db,
    )
    return {"ok": True, "scripts": scripts, "count": len(scripts)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
