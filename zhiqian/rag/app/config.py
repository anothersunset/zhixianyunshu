from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RAG_", env_file=".env", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8001
    data_dir: str = "/data"

    embedding_dim: int = 1024
    bm25_top_k: int = 50
    rerank_top_n: int = 5

    # BGE-M3
    use_bge_m3: bool = True
    bge_model: str = "BAAI/bge-m3"
    bge_fp16: bool = True
    bge_device: str = ""

    # Reranker
    use_reranker: bool = True
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_fp16: bool = True

    # Qdrant + RRF
    use_qdrant: bool = True
    qdrant_url: str = "http://qdrant:6333"
    qdrant_api_key: str = ""
    rrf_k: int = 60

    # v2-step-06: Chunking
    # 默认策略 semantic；/ingest 请求可在单次调用中覆盖
    chunk_strategy: str = "semantic"  # semantic / late / none
    chunk_sim_threshold: float = 0.62
    chunk_max_chars: int = 1200
    late_chunk_max_chars: int = 600
    late_chunk_overlap: int = 80


settings = Settings()
