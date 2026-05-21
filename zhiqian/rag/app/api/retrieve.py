from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging

log = logging.getLogger(__name__)
router = APIRouter()

# v2-step-05：/retrieve 真接入 HybridRetriever。返回多路检索 + RRF + 可选重排的丝滑结果。


class RetrieveReq(BaseModel):
    collection: str = "zhiqian-default"
    query: str
    top_k: int = 5
    filters: Optional[Dict[str, Any]] = None


class RetrieveItem(BaseModel):
    id: str
    text: str
    score: float
    source: str
    meta: Optional[Dict[str, Any]] = None
    rrf_score: Optional[float] = None
    rerank_score: Optional[float] = None
    channels: Optional[Dict[str, float]] = None


class RetrieveResp(BaseModel):
    items: List[RetrieveItem]
    capabilities: Dict[str, Any]


def _retriever():
    raise RuntimeError("retriever 未注入")


@router.post("", response_model=RetrieveResp)
async def retrieve(req: RetrieveReq, r=Depends(_retriever)) -> RetrieveResp:
    chunks = r.search(req.query, top_k=req.top_k, filters=req.filters)
    items = [RetrieveItem(**{k: v for k, v in c.items() if k in RetrieveItem.model_fields}) for c in chunks]
    return RetrieveResp(items=items, capabilities=r.capabilities())
