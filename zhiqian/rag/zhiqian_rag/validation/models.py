from typing import List, Optional, Dict
from pydantic import BaseModel

class PatchItem(BaseModel):
    unit_id: str
    category: str
    target_file: str
    unified_diff: str
    confidence: float
    requires_human_review: bool = False
    evidence_ids: List[str] = []
    rationale: Optional[str] = None

class PatchSet(BaseModel):
    task_id: str
    total: int
    avg_confidence: float
    review_required: int
    results: List[PatchItem]
    by_category: Dict[str, List[PatchItem]] = {}

class ValidationScript(BaseModel):
    script_id: str
    kind: str                # sql_val / unit_hint / smoke_curl / compile_gate
    target_path: str         # 落盘相对路径
    content: str
    related_unit_ids: List[str] = []

class ValidationBundle(BaseModel):
    task_id: str
    scripts: List[ValidationScript]
