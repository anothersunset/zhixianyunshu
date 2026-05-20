from typing import List, Dict, Any

class SelfRag:
    def __init__(self, retriever, reranker, critic, rewriter, max_loops: int = 2):
        self.retriever = retriever
        self.reranker = reranker
        self.critic = critic
        self.rewriter = rewriter
        self.max_loops = max_loops

    def run(self, collection: str, query: str) -> Dict[str, Any]:
        q = query
        history: List[Dict[str, Any]] = []
        top: List[Dict[str, Any]] = []
        for loop in range(self.max_loops + 1):
            cand = self.retriever.retrieve(collection, q, k=50)
            top = self.reranker.rerank(q, cand, top_n=5)
            score = self.critic.score(q, top)
            history.append({"loop": loop, "query": q, "score": score})
            if score["sufficient"]:
                return {"answer_chunks": top, "history": history}
            q = self.rewriter.rewrite(q, top, score["reason"])
        return {"answer_chunks": top, "history": history, "fallback": True}
