from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging

from app.core.observability import get_langfuse

log = logging.getLogger(__name__)
router = APIRouter(prefix="/retrieve", tags=["retrieve"])

# v2-step-05: /retrieve 真接入 HybridRetriever。返回多路检索 + RRF + 可选重排的丝滑结果。
# v2-step-07: 包一层 'rag.retrieve_api' trace,透传给 retriever.search 避免双 trace。


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
    lf = get_langfuse()
    with lf.trace(
        "rag.retrieve_api",
        input={"query": req.query, "top_k": req.top_k, "collection": req.collection},
        tags=["retrieve"],
    ) as tr:
        chunks = r.search(
            req.query,
            top_k=req.top_k,
            filters=req.filters,
            parent_trace=tr,
        )
        tr.output({"items": len(chunks), "ids": [c.get("id") for c in chunks]})
    items = [RetrieveItem(**{k: v for k, v in c.items() if k in RetrieveItem.model_fields}) for c in chunks]
    return RetrieveResp(items=items, capabilities=r.capabilities())
