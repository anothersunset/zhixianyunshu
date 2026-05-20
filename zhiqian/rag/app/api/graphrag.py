from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict, Any

router = APIRouter()

class GraphReq(BaseModel):
    entity: str
    hops: int = 2

class GraphResp(BaseModel):
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

@router.post("", response_model=GraphResp)
async def graphrag(req: GraphReq) -> GraphResp:
    return GraphResp()
