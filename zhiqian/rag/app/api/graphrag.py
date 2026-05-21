"""
v2-step-13: GraphRAG HTTP 入口。
所有端点: POST /index, POST /query/local, POST /query/global, GET /stats。
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


class GraphNodeIn(BaseModel):
    id: str
    type: str = "unknown"
    label: str = ""
    text: str = ""


class GraphEdgeIn(BaseModel):
    src: str
    dst: str
    type: str = "related"
    weight: float = 1.0


class IndexReq(BaseModel):
    nodes: List[GraphNodeIn]
    edges: List[GraphEdgeIn] = Field(default_factory=list)


class LocalQueryReq(BaseModel):
    question: str
    max_entities: int = 3
    hop: int = 1


class GlobalQueryReq(BaseModel):
    question: str
    max_reports: int = 3


def _index_dep():
    raise NotImplementedError("GraphRagIndex 未注入")


@router.post("/index")
def index(req: IndexReq, index = Depends(_index_dep)):
    stats = index.build(
        [n.dict() for n in req.nodes],
        [e.dict() for e in req.edges],
    )
    return {"ok": True, **stats}


@router.post("/query/local")
def query_local(req: LocalQueryReq, index = Depends(_index_dep)):
    if not index.nodes:
        raise HTTPException(409, "请先 POST /graphrag/index 建索引")
    return {"ok": True, **index.query_local(req.question, max_entities=req.max_entities, hop=req.hop)}


@router.post("/query/global")
def query_global(req: GlobalQueryReq, index = Depends(_index_dep)):
    if not index.communities:
        raise HTTPException(409, "请先 POST /graphrag/index 建索引")
    return {"ok": True, **index.query_global(req.question, max_reports=req.max_reports)}


@router.get("/stats")
def stats(index = Depends(_index_dep)):
    return {"ok": True, **index.stats()}
