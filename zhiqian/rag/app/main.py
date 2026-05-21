"""v2-step-27: 主入口, 注册全部 router。"""
from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    health, query as query_api, validation, rerank, ingest, retrieve,
    transpile, crag, graphrag, structured, mcp as mcp_api,
    tts as tts_api, reports as reports_api,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="ZhiQian RAG", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
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
