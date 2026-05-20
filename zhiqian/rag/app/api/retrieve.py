from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

router = APIRouter()

class RetrieveReq(BaseModel):
    collection: str
    query: str
    top_k: int = 50
    enable_self_rag: bool = False

class RetrieveItem(BaseModel):
    id: str
    text: Optional[str] = None
    score: float
    source: Optional[Dict[str, Any]] = None

class RetrieveResp(BaseModel):
    items: List[RetrieveItem]
    history: List[Dict[str, Any]] = []

@router.post("", response_model=RetrieveResp)
async def retrieve(req: RetrieveReq) -> RetrieveResp:
    return RetrieveResp(items=[], history=[])
