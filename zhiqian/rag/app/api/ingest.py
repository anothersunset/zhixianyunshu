from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Dict, Any
import logging

log = logging.getLogger(__name__)
router = APIRouter()

# v2-step-05：/ingest 真接入。调用者需传 docs (id/text/source/meta)。背后走 HybridRetriever.add，
# 同时更新 BM25 内存与 Qdrant（如可用）。
# 退化：Qdrant 不可用时仅更新内存与 BM25，仍返回 inserted 计数。


class IngestReq(BaseModel):
    collection: str = "zhiqian-default"
    docs: List[Dict[str, Any]]


class IngestResp(BaseModel):
    inserted: int
    capabilities: Dict[str, Any]


def _retriever():
    # 面向测试可覆盖的指针。运行时由 main.py 重新绑定为全局 retriever。
    raise RuntimeError("retriever 未注入")


@router.post("", response_model=IngestResp)
async def ingest(req: IngestReq, r=Depends(_retriever)) -> IngestResp:
    n = r.add(req.docs)
    return IngestResp(inserted=n, capabilities=r.capabilities())
