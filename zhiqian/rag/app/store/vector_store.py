import chromadb
from typing import List, Dict, Any
from app.core.embedder import Embedder

class VectorStore:
    def __init__(self, path: str, embedder: Embedder):
        self.client = chromadb.PersistentClient(path=path)
        self.embedder = embedder

    def collection(self, name: str):
        return self.client.get_or_create_collection(name)

    def upsert(self, name: str, docs: List[Dict[str, Any]]):
        col = self.collection(name)
        ids = [d["id"] for d in docs]
        texts = [d["text"] for d in docs]
        metas = [d.get("meta", {}) for d in docs]
        embs = self.embedder.encode(texts)
        col.upsert(ids=ids, documents=texts, metadatas=metas, embeddings=embs)

    def query(self, name: str, query: str, k: int = 50):
        col = self.collection(name)
        emb = self.embedder.encode([query])[0]
        return col.query(query_embeddings=[emb], n_results=k)
