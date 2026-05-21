from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging

from app.config import settings
from app.core.chunker import pick_chunker
from app.core.bge_m3 import BgeM3Embedder

log = logging.getLogger(__name__)
router = APIRouter()

# v2-step-06：/ingest 接收原始文档，按 strategy (semantic / late / none) 切块后入库。
# - semantic: 按句子相似度合并，不携 embedding（交给 retriever 统一 encode）
# - late: 全文 encode + chunk 内 token 池化，embedding 随 doc 一起传入库，省一次 encode
# - none: 原文不切块、原样入库


class IngestReq(BaseModel):
    collection: str = "zhiqian-default"
    docs: List[Dict[str, Any]]
    strategy: Optional[str] = None  # semantic / late / none。None 时用 settings.chunk_strategy


class IngestResp(BaseModel):
    docs_received: int
    chunks_inserted: int
    strategy_used: str
    capabilities: Dict[str, Any]


def _retriever():
    raise RuntimeError("retriever 未注入")


@router.post("", response_model=IngestResp)
async def ingest(req: IngestReq, r=Depends(_retriever)) -> IngestResp:
    strategy = (req.strategy or settings.chunk_strategy or "semantic").lower()
    embedder: Optional[BgeM3Embedder] = getattr(r, "_embedder", None)
    chunker = pick_chunker(
        strategy,
        embedder=embedder,
        sim_threshold=settings.chunk_sim_threshold,
        max_chars=settings.chunk_max_chars,
        late_max_chars=settings.late_chunk_max_chars,
        late_overlap=settings.late_chunk_overlap,
        dim=settings.embedding_dim,
    )
    all_chunks: List[Dict[str, Any]] = []
    for d in req.docs:
        doc_id = d.get("id") or ""
        text = d.get("text") or ""
        meta_in = d.get("meta") or {}
        source = d.get("source") or "manual"
        if chunker is None:
            # strategy=none：原样入库
            all_chunks.append(d)
            continue
        pieces = chunker.chunk(text, doc_id=doc_id)
        if not pieces:
            continue
        for p in pieces:
            merged_meta = {**meta_in, **p.get("meta", {})}
            all_chunks.append({
                "id": p["id"],
                "text": p["text"],
                "source": source,
                "meta": merged_meta,
                **({"embedding": p["embedding"]} if "embedding" in p else {}),
            })
    inserted = r.add(all_chunks)
    return IngestResp(
        docs_received=len(req.docs),
        chunks_inserted=inserted,
        strategy_used=strategy,
        capabilities=r.capabilities(),
    )
