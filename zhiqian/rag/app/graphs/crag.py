"""
v2-step-12: CRAG (Corrective RAG) 运行时。

自实现轻量 StateGraph (~110 行), 不依赖 langgraph。
不同于简单线型流水线, 本模块是路由型 DAG, 有条件分支。

节点拓扑:
  retrieve → evaluate → (按 route 分三路):
    correct   : refine → generate
    ambiguous : refine 与 web_search 串行 → merge → generate
    incorrect : web_search → refine → generate

场景例:
  question = '什么是 openGauss IFNULL?'
  retrieve 返中 doc-2 (高重叠) → evaluate=0.6 (correct) → refine → generate 用本地
  question = '什么是 Quantum Chromodynamics?'
  retrieve 不中 → evaluate=0.0 (incorrect) → web_search → refine → generate
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional

import httpx

from .state import CragState, new_state
from .evaluator import RetrievalEvaluator
from .refiner import KnowledgeRefiner
from .web_search import WebSearcher

log = logging.getLogger("crag.runner")


class CragRunner:
    """CRAG 主在器。复用 HybridRetriever, 不重复创建。"""

    def __init__(self, retriever, evaluator: Optional[RetrievalEvaluator] = None,
                 refiner: Optional[KnowledgeRefiner] = None,
                 web_searcher: Optional[WebSearcher] = None):
        self.retriever = retriever
        self.evaluator = evaluator or RetrievalEvaluator()
        self.refiner = refiner or KnowledgeRefiner()
        self.web_searcher = web_searcher or WebSearcher()
        # Langfuse 可选: 避免硬依赖
        try:
            from app.core.observability import get_langfuse
            self._lf = get_langfuse()
        except Exception:
            self._lf = None

    # ============ 单个节点 ============

    def _node_retrieve(self, state: CragState, parent_trace=None) -> CragState:
        t0 = time.time()
        q = state["question"]
        top_k = state.get("top_k", 5)
        docs = self.retriever.search(q, top_k=top_k, parent_trace=parent_trace) or []
        state["docs"] = docs
        self._log_step(state, "retrieve", t0, {"top_k": top_k}, {"n_docs": len(docs)})
        return state

    def _node_evaluate(self, state: CragState) -> CragState:
        t0 = time.time()
        conf = self.evaluator.score(state["question"], state["docs"])
        route = self.evaluator.route(conf)
        state["confidence"] = conf
        state["route"] = route
        self._log_step(state, "evaluate", t0,
                       {"upper": self.evaluator.upper, "lower": self.evaluator.lower},
                       {"confidence": conf, "route": route})
        return state

    def _node_refine(self, state: CragState) -> CragState:
        t0 = time.time()
        all_docs = list(state.get("docs") or []) + list(state.get("web_docs") or [])
        strips = self.refiner.refine(state["question"], all_docs)
        state["refined"] = strips
        self._log_step(state, "refine", t0, {"n_docs": len(all_docs)},
                       {"n_strips": len(strips)})
        return state

    def _node_web_search(self, state: CragState) -> CragState:
        t0 = time.time()
        if not state.get("use_web", True):
            state["web_docs"] = []
            self._log_step(state, "web_search", t0, {}, {"skipped": True})
            return state
        web_docs = self.web_searcher.search(state["question"])
        state["web_docs"] = web_docs
        self._log_step(state, "web_search", t0, {}, {"n_web": len(web_docs)})
        return state

    def _node_generate(self, state: CragState) -> CragState:
        t0 = time.time()
        strips = state.get("refined") or []
        question = state["question"]
        api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if api_key and strips:
            try:
                answer = self._call_deepseek(question, strips, api_key)
                state["answer"] = answer
                self._log_step(state, "generate", t0,
                               {"backend": "deepseek", "n_strips": len(strips)},
                               {"answer_chars": len(answer)})
                return state
            except Exception as e:
                log.warning("[crag] DeepSeek 调用失败, 降级拼接: %r", e)
        # 降级: 拼接式答案
        if not strips:
            answer = "根据现有上下文未能得出明确结论, 请补充更多语料。"
        else:
            joined = "\n- " + "\n- ".join(strips[:5])
            answer = f"根据检索到的上下文, 针对 '{question}' 的要点如下:{joined}"
        state["answer"] = answer
        self._log_step(state, "generate", t0,
                       {"backend": "template-fallback", "n_strips": len(strips)},
                       {"answer_chars": len(answer)})
        return state

    def _call_deepseek(self, question: str, strips, api_key: str) -> str:
        base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
        model = os.environ.get("DEEPSEEK_CHAT_MODEL", "deepseek-chat")
        context = "\n".join(f"[{i+1}] {s}" for i, s in enumerate(strips[:15]))
        messages = [
            {"role": "system", "content": "你是严谨的技术助手, 只根据上下文回答, 不胡说八道。未提及的明确说「上下文未提及」。"},
            {"role": "user", "content": f"问题: {question}\n\n上下文:\n{context}\n\n请给出中文回答。"},
        ]
        with httpx.Client(timeout=20.0) as c:
            r = c.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": messages, "temperature": 0.2, "max_tokens": 800},
            )
            r.raise_for_status()
            data = r.json()
        return data["choices"][0]["message"]["content"].strip()

    # ============ 调度 ============

    def run(self, question: str, top_k: int = 5, use_web: bool = True) -> CragState:
        """同步 run, 返回最终 state。所有节点都在同一 trace 下。"""
        state = new_state(question, top_k=top_k, use_web=use_web)
        # Langfuse trace (可选)
        if self._lf and getattr(self._lf, "available", False):
            with self._lf.trace("rag.crag", input={"question": question, "top_k": top_k},
                                 metadata={"use_web": use_web}, tags=["crag"]) as tr:
                state["trace_id"] = getattr(tr, "id", None) or getattr(tr, "trace_id", None)
                state = self._dispatch(state, parent_trace=tr)
                tr.output({
                    "route": state.get("route"),
                    "confidence": state.get("confidence"),
                    "n_strips": len(state.get("refined") or []),
                    "answer_chars": len(state.get("answer") or ""),
                })
        else:
            state = self._dispatch(state, parent_trace=None)
        return state

    def _dispatch(self, state: CragState, parent_trace=None) -> CragState:
        # 1. retrieve
        state = self._node_retrieve(state, parent_trace=parent_trace)
        # 2. evaluate
        state = self._node_evaluate(state)
        route = state["route"]
        # 3. 路由分支
        if route == "correct":
            state = self._node_refine(state)
        elif route == "ambiguous":
            state = self._node_web_search(state)
            state = self._node_refine(state)
        else:  # incorrect
            state = self._node_web_search(state)
            state = self._node_refine(state)
        # 4. generate
        state = self._node_generate(state)
        return state

    def _log_step(self, state: CragState, node: str, started_at: float,
                  inp: Dict[str, Any], out: Dict[str, Any]) -> None:
        steps = state.setdefault("steps", [])
        steps.append({
            "node": node,
            "started_at": started_at,
            "elapsed_ms": round((time.time() - started_at) * 1000, 2),
            "input": inp,
            "output": out,
        })
