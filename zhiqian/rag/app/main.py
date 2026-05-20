from fastapi import FastAPI
from app.api import health, ingest, retrieve, rerank, graphrag

app = FastAPI(title="zhiqian-rag", version="0.1.0")
app.include_router(health.router, tags=["health"])
app.include_router(ingest.router, prefix="/api/ingest", tags=["ingest"])
app.include_router(retrieve.router, prefix="/api/retrieve", tags=["retrieve"])
app.include_router(rerank.router, prefix="/api/rerank", tags=["rerank"])
app.include_router(graphrag.router, prefix="/api/graphrag", tags=["graphrag"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=True)
