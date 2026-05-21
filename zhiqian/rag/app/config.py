from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RAG_", env_file=".env", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8001
    data_dir: str = "/data"

    # v2-step-04：从 768 提升到 1024（与 BGE-M3 原生一致）。hash 占位也发 1024，避免 Chroma 维度冲突。
    embedding_dim: int = 1024
    bm25_top_k: int = 50
    rerank_top_n: int = 5

    # v2-step-04：BGE-M3 配置
    use_bge_m3: bool = True
    bge_model: str = "BAAI/bge-m3"
    bge_fp16: bool = True
    bge_device: str = ""  # 空 → 自动；cpu / cuda:0 等

    # v2-step-04：Reranker 配置
    use_reranker: bool = True
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_fp16: bool = True


settings = Settings()
