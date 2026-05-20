from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RAG_", env_file=".env", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8001
    data_dir: str = "/data"
    embedding_dim: int = 768
    bm25_top_k: int = 50
    rerank_top_n: int = 5


settings = Settings()
