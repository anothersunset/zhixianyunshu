"""
v2-step-11: pytest fixtures 。

- client: FastAPI TestClient (在进程内起 app, 不起真端口)
- golden_set: 从 data/golden_set.jsonl 加载 20 条黄金集
- ragas_llm: 如果有 DEEPSEEK_API_KEY, 构造 OpenAI compatible ChatOpenAI 作为 RAGAS 判官; 否则 None
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Generator, List, Optional

import pytest

DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture(scope="session")
def golden_set() -> List[dict]:
    """加载 20 条黄金集。每条含：id, kind, question, [expected_*]。"""
    path = DATA_DIR / "golden_set.jsonl"
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        items.append(json.loads(line))
    assert len(items) >= 20, f"golden set 应有 ≥ 20 条, 现 {len(items)}"
    return items


@pytest.fixture(scope="session")
def client() -> Generator[Any, None, None]:
    """FastAPI TestClient, 全会话复用 (避免多次加载模型)。"""
    try:
        from fastapi.testclient import TestClient
        from app.main import app  # type: ignore
    except Exception as e:
        pytest.skip(f"FastAPI app 不可加载: {e}")
        return
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def ragas_llm() -> Optional[Any]:
    """构造 RAGAS 使用的 LLM 判官。无 key 返 None, 测试将 skipif。"""
    key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        return None
    try:
        from langchain_openai import ChatOpenAI  # type: ignore
        from ragas.llms import LangchainLLMWrapper  # type: ignore
    except Exception:
        return None
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    model = os.environ.get("DEEPSEEK_CHAT_MODEL", "deepseek-chat")
    llm = ChatOpenAI(model=model, api_key=key, base_url=base_url, temperature=0.0, max_tokens=512)
    return LangchainLLMWrapper(llm)


@pytest.fixture(scope="session")
def ragas_embeddings() -> Optional[Any]:
    """RAGAS 处下另需 embeddings (算 answer_similarity 等)。

    优先用 BGE-M3 (与产品一致); 装不上就跳。"""
    try:
        from langchain_huggingface import HuggingFaceEmbeddings  # type: ignore
        from ragas.embeddings import LangchainEmbeddingsWrapper  # type: ignore
    except Exception:
        return None
    model_name = os.environ.get("RAG_BGE_MODEL", "BAAI/bge-m3")
    try:
        emb = HuggingFaceEmbeddings(model_name=model_name)
    except Exception:
        return None
    return LangchainEmbeddingsWrapper(emb)
