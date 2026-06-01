"""v2-step-01: /query HTTP 入口。BM25 + 向量混合检索 + Self-RAG critic。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter()


class QueryReq(BaseModel):
    question: str
    top_k: int = 5
    collection: str = "zhiqian-default"


class ChunkResp(BaseModel):
    id: str
    text: str
    score: float
    source: str
    meta: Optional[Dict[str, Any]] = None


class CritiqueResp(BaseModel):
    score: float
    verdict: str
    reasons: List[str] = []
    suggest_rewrite: bool = False
    stats: Optional[Dict[str, Any]] = None


class QueryResp(BaseModel):
    question: str
    rewritten: str
    chunks: List[ChunkResp]
    critique: CritiqueResp


def _retriever():
    raise NotImplementedError("Retriever 未注入")


def _critic():
    raise NotImplementedError("Critic 未注入")


@router.post("/query", response_model=QueryResp)
async def query(req: QueryReq, retriever=Depends(_retriever), critic=Depends(_critic)):
    chunks = retriever.search(req.question, top_k=req.top_k)
    critique = critic.evaluate(req.question, chunks)
    return QueryResp(
        question=req.question,
        rewritten=req.question,
        chunks=[ChunkResp(**c) for c in chunks],
        critique=CritiqueResp(**critique),
    )
