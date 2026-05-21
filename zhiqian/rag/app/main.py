"""v2-step-23/26: 主入口, 注册 MCP + TTS router。"""
from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    health, query as query_api, validation, rerank, ingest, retrieve,
    transpile, crag, graphrag, structured, mcp as mcp_api, tts as tts_api,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="ZhiQian RAG", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)
app.include_router(health.router)
app.include_router(query_api.router)
app.include_router(validation.router)
app.include_router(rerank.router)
app.include_router(ingest.router)
app.include_router(retrieve.router)
app.include_router(transpile.router)
app.include_router(crag.router)
app.include_router(graphrag.router)
app.include_router(structured.router)
app.include_router(mcp_api.router)
app.include_router(tts_api.router)


@app.get("/")
async def root():
    return {
        "name": "ZhiQian RAG",
        "version": "1.0.0",
        "capabilities": {
            "crag": True, "graphrag": True, "structured": True,
            "mcp": True, "tts": True
        }
    }
