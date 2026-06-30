"""v2-step-27: 主入口, 注册全部 router。"""
from __future__ import annotations
import logging
import os
import sys
import traceback
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    health, query as query_api, validation, rerank, ingest, retrieve,
    transpile, crag, graphrag, structured, mcp as mcp_api,
    tts as tts_api, reports as reports_api,
)
from app.pipelines.retriever import HybridRetriever
from app.pipelines.critic import SelfRagCritic
from app.graphs.graphrag import GraphRagIndex
from app.graphs.kb_graph_builder import build_graph_from_docs

# ─── 日志持久化 ───
_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
_LOG_FILE = os.path.join(_LOG_DIR, "rag_service.log")
_file_handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
_file_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
_file_handler.setLevel(logging.DEBUG)
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
_console_handler.setLevel(logging.INFO)
logging.root.setLevel(logging.DEBUG)
logging.root.addHandler(_file_handler)
logging.root.addHandler(_console_handler)

log = logging.getLogger(__name__)

# ─── 内存保护 ───
_MEMORY_LIMIT_MB = int(os.environ.get("RAG_MEMORY_LIMIT_MB", "4500"))


def _get_memory_mb() -> float:
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
    except Exception:
        return 0.0


@asynccontextmanager
async def lifespan(app: FastAPI):
    import gc
    log.info("[lifespan] RAG 服务启动中... PID=%d, 内存限制=%dMB", os.getpid(), _MEMORY_LIMIT_MB)
    log.info("[lifespan] 初始内存: %.1fMB", _get_memory_mb())

    # 初始化 HybridRetriever 并注入到 retrieve/ingest 的依赖
    try:
        retriever = HybridRetriever()
        log.info("[lifespan] HybridRetriever initialized, capabilities=%s", retriever.capabilities())
        log.info("[lifespan] Retriever 初始化后内存: %.1fMB", _get_memory_mb())
    except Exception as e:
        log.error("[lifespan] HybridRetriever init failed: %s, starting with empty retriever\n%s",
                  e, traceback.format_exc())
        from app.pipelines.retriever import HybridRetriever as _HR
        retriever = _HR.__new__(_HR)
        retriever.docs = []
        retriever._bm25 = None
        retriever._by_id = {}
        retriever._reranker = None
        retriever._embedder = None
        retriever._qdrant = None
        retriever.collection = "zhiqian-default"
    app.state.retriever = retriever

    # 初始化 SelfRAG critic
    critic = SelfRagCritic()
    log.info("[lifespan] SelfRagCritic initialized")
    app.state.critic = critic

    # v2-step-13: 初始化 GraphRAG 索引（从 KB 文档提取实体与关系）
    try:
        graph_index = GraphRagIndex(max_community_size=20)
        graph_data = build_graph_from_docs(retriever.docs)
        stats = graph_index.build(graph_data["nodes"], graph_data["edges"])
        log.info("[lifespan] GraphRAG index built: n_nodes=%d n_edges=%d n_communities=%d",
                 stats["n_nodes"], stats["n_edges"], stats["n_communities"])
        retriever.graph_index = graph_index
    except Exception as e:
        log.warning("[lifespan] GraphRAG index build failed: %s, full mode = crag\n%s",
                    e, traceback.format_exc())
        retriever.graph_index = None

    gc.collect()
    log.info("[lifespan] 初始化完成, 最终内存: %.1fMB", _get_memory_mb())

    # 使用 FastAPI 的 dependency_overrides 机制注入
    app.dependency_overrides[retrieve._retriever] = lambda: retriever
    app.dependency_overrides[ingest._retriever] = lambda: retriever
    app.dependency_overrides[query_api._retriever] = lambda: retriever
    app.dependency_overrides[query_api._critic] = lambda: critic
    # 注入 GraphRAG index 到 graphrag API
    app.dependency_overrides[graphrag._index_dep] = lambda: graph_index if retriever.graph_index and retriever.graph_index.nodes else None

    yield

    log.info("[lifespan] RAG 服务关闭中...")


app = FastAPI(title="ZhiQian RAG", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


@app.middleware("http")
async def catch_exceptions_middleware(request: Request, call_next):
    """全局异常捕获 + 内存保护中间件。"""
    # 内存保护：超过阈值时拒绝新请求，防止 OOM 崩溃
    mem_mb = _get_memory_mb()
    if mem_mb > _MEMORY_LIMIT_MB:
        log.error("[middleware] 内存 %.0fMB 超过限制 %dMB，拒绝请求", mem_mb, _MEMORY_LIMIT_MB)
        return JSONResponse(
            status_code=503,
            content={"error": "memory_limit_exceeded",
                     "detail": f"Memory {mem_mb:.0f}MB > limit {_MEMORY_LIMIT_MB}MB",
                     "retry_after": 30},
            headers={"Retry-After": "30"},
        )
    try:
        return await call_next(request)
    except Exception as e:
        log.error("[middleware] 未捕获异常: %s\n%s", e, traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"error": "internal_server_error", "detail": str(e)[:200]},
        )
for r in (health, query_api, validation, rerank, ingest, retrieve,
          transpile, crag, graphrag, structured, mcp_api, tts_api, reports_api):
    app.include_router(r.router)


@app.get("/")
async def root():
    return {
        "name": "ZhiQian RAG",
        "version": "1.0.0",
        "capabilities": {
            "crag": True, "graphrag": True, "structured": True,
            "mcp": True, "tts": True, "reports": True
        }
    }
