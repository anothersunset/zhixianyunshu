from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict, Any

router = APIRouter()

class RerankReq(BaseModel):
    query: str
    candidates: List[Dict[str, Any]]
    top_n: int = 5

class RerankResp(BaseModel):
    items: List[Dict[str, Any]]

@router.post("", response_model=RerankResp)
async def rerank(req: RerankReq) -> RerankResp:
    return RerankResp(items=req.candidates[: req.top_n])
