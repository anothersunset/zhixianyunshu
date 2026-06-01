from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging

from app.config import settings
from app.core.chunker import pick_chunker
from app.core.bge_m3 import BgeM3Embedder
from app.core.observability import get_langfuse

log = logging.getLogger(__name__)
router = APIRouter(prefix="/ingest", tags=["ingest"])

# v2-step-06: /ingest 接收原始文档,按 strategy (semantic / late / none) 切块后入库。
# v2-step-07: 全链 Langfuse 埋点 — pick_chunker / chunk.run / retriever.add 三段 span。


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
    lf = get_langfuse()
    with lf.trace(
        "rag.ingest",
        input={"docs": len(req.docs), "strategy": strategy, "collection": req.collection},
        tags=["ingest"],
    ) as tr:
        embedder: Optional[BgeM3Embedder] = getattr(r, "_embedder", None)
        with tr.span("pick_chunker", input={"strategy": strategy}) as sp:
            chunker = pick_chunker(
                strategy,
                embedder=embedder,
                sim_threshold=settings.chunk_sim_threshold,
                max_chars=settings.chunk_max_chars,
                late_max_chars=settings.late_chunk_max_chars,
                late_overlap=settings.late_chunk_overlap,
                dim=settings.embedding_dim,
            )
            sp.output({"chunker": type(chunker).__name__ if chunker else "none"})

        all_chunks: List[Dict[str, Any]] = []
        with tr.span("chunk.run", input={"docs": len(req.docs)}) as sp:
            for d in req.docs:
                doc_id = d.get("id") or ""
                text = d.get("text") or ""
                meta_in = d.get("meta") or {}
                source = d.get("source") or "manual"
                if chunker is None:
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
            sp.output({"chunks": len(all_chunks)})

        with tr.span("retriever.add", input={"chunks": len(all_chunks)}) as sp:
            inserted = r.add(all_chunks)
            sp.output({"inserted": inserted})

        tr.output({
            "docs_received": len(req.docs),
            "chunks_inserted": inserted,
            "strategy": strategy,
        })

    return IngestResp(
        docs_received=len(req.docs),
        chunks_inserted=inserted,
        strategy_used=strategy,
        capabilities=r.capabilities(),
    )
