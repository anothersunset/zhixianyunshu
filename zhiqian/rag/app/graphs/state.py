"""
v2-step-12: CRAG 状态机 state。

价值:现代可观测型 RAG 都需 explicit state, 避免隐藏在闭包里那种「为什么变了」问题。
CRAG = Corrective Retrieval-Augmented Generation (Yan et al. 2024)
与 Self-RAG 区别: CRAG 是检索后“评价-路由-修复”, Self-RAG 是生成中 reflection。
CRAG 更少 LLM 调用, 更适合产品环境。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class CragStepLog(TypedDict, total=False):
    """单个节点的审计日志。用于调试与 Langfuse 上报。"""
    node: str           # retrieve / evaluate / refine / web_search / generate
    started_at: float   # unix ts
    elapsed_ms: float
    input: Dict[str, Any]
    output: Dict[str, Any]
    note: str


class CragState(TypedDict, total=False):
    # 输入
    question: str
    top_k: int
    use_web: bool       # 是否允许 web_search 补充 (未设 默认 True)
    trace_id: Optional[str]

    # 检索阶段
    docs: List[Dict[str, Any]]          # 本地检索结果
    web_docs: List[Dict[str, Any]]      # web_search 补充结果

    # 评价与路由
    confidence: float                   # 0-1, 越高越可靠
    route: str                          # 'correct' | 'ambiguous' | 'incorrect'

    # 修复与生成
    refined: List[str]                  # decompose-recompose 后的 strips
    answer: str                         # 最终答案
    citations: List[Dict[str, Any]]

    # 审计
    steps: List[CragStepLog]


def new_state(question: str, top_k: int = 5, use_web: bool = True, trace_id: Optional[str] = None) -> CragState:
    """创建初始 state。出口给 api/crag.py 使用。"""
    s: CragState = {
        "question": question,
        "top_k": top_k,
        "use_web": use_web,
        "trace_id": trace_id,
        "docs": [],
        "web_docs": [],
        "confidence": 0.0,
        "route": "",
        "refined": [],
        "answer": "",
        "citations": [],
        "steps": [],
    }
    return s
