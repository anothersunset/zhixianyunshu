from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    embed_model: str = "BAAI/bge-m3"
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    chroma_path: str = "./.chroma"
    top_k: int = 50
    top_n: int = 5
    hyde_enabled: bool = True

    class Config:
        env_prefix = "ZHIQIAN_RAG_"

settings = Settings()
