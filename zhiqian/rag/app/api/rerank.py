from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging

from app.config import settings
from app.core.reranker import CrossEncoderReranker

log = logging.getLogger(__name__)
router = APIRouter()

# v2-step-04：独立的 reranker 端点。多个调用者可复用同一个加载过的模型。
_RERANKER: Optional[CrossEncoderReranker] = None


def _get_reranker() -> CrossEncoderReranker:
    global _RERANKER
    if _RERANKER is None:
        _RERANKER = CrossEncoderReranker(
            model_path=settings.reranker_model, use_fp16=settings.reranker_fp16
        )
    return _RERANKER


class RerankReq(BaseModel):
    query: str
    candidates: List[Dict[str, Any]]  # 必含 text 字段
    top_n: int = 5
    text_field: str = "text"


class RerankItem(BaseModel):
    index: int
    score: float
    item: Dict[str, Any]


class RerankResp(BaseModel):
    available: bool
    model: str
    items: List[RerankItem]


@router.post("", response_model=RerankResp)
async def rerank(req: RerankReq) -> RerankResp:
    rr = _get_reranker()
    if not req.candidates:
        return RerankResp(available=rr.available, model=settings.reranker_model, items=[])
    texts = [c.get(req.text_field, "") for c in req.candidates]
    pairs = rr.rerank(req.query, texts, top_n=req.top_n)
    items = [RerankItem(index=i, score=s, item=req.candidates[i]) for i, s in pairs]
    return RerankResp(available=rr.available, model=settings.reranker_model, items=items)
