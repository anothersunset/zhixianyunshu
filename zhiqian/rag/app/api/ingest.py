from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict, Any

router = APIRouter()

class IngestReq(BaseModel):
    collection: str
    docs: List[Dict[str, Any]]

class IngestResp(BaseModel):
    inserted: int

@router.post("", response_model=IngestResp)
async def ingest(req: IngestReq) -> IngestResp:
    # M2 骨架：M4 接入真实入库
    return IngestResp(inserted=0)
