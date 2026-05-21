"""
v2-step-13: GraphRAG 索引与查询。

Index 流程:
  nodes + edges → build adjacency → CommunityDetector → 为每个 community 生报告 (纯文本, 可选 LLM 提炼)

Query 流程:
  local : keyword 匹配实体 → BFS 1-hop → 邻居 text 拼接
  global: query 与 community report keyword 重叠 → top-3 报告拼接
"""
from __future__ import annotations

import os
import re
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .community import CommunityDetector

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[\u4e00-\u9fff]")
_STOPS = {"the", "and", "or", "of", "to", "in", "for", "on", "is", "a", "an", "的", "是", "了", "和"}


def _tokenize(s: str) -> List[str]:
    return [t.lower() for t in _TOKEN_RE.findall(s or "") if t.lower() not in _STOPS]


@dataclass
class GraphNode:
    id: str
    type: str           # File / Class / Method / Table / Column
    label: str          # 人读名称
    text: str = ""      # 摘要 / 注释 / signature

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "type": self.type, "label": self.label, "text": self.text}


@dataclass
class GraphEdge:
    src: str
    dst: str
    type: str = "related"
    weight: float = 1.0


@dataclass
class CommunityReport:
    id: str                                  # c-0, c-1, ...
    title: str                               # 「Order 模块 8 个方法」
    summary: str                             # 多行文本
    keywords: List[str]                      # top-N 高频 token
    node_ids: List[str]
    type_breakdown: Dict[str, int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "keywords": self.keywords,
            "node_count": len(self.node_ids),
            "type_breakdown": self.type_breakdown,
        }


class GraphRagIndex:
    """在内存趋 100k 节点 OK。Phase 3 上 JanusGraph/KuzuDB。"""

    def __init__(self, max_community_size: int = 50):
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []
        self.adj: Dict[str, Set[str]] = defaultdict(set)
        self.community_map: Dict[str, str] = {}              # node_id -> c-N
        self.communities: Dict[str, CommunityReport] = {}    # c-N -> report
        self.detector = CommunityDetector(max_community_size=max_community_size)

    def build(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> Dict[str, Any]:
        # 1. 装载 nodes
        self.nodes = {}
        for n in nodes:
            nid = str(n["id"])
            self.nodes[nid] = GraphNode(
                id=nid, type=str(n.get("type", "unknown")),
                label=str(n.get("label") or nid),
                text=str(n.get("text") or ""),
            )
        # 2. 装载 edges
        self.edges = []
        self.adj = defaultdict(set)
        for e in edges:
            src, dst = str(e["src"]), str(e["dst"])
            if src not in self.nodes or dst not in self.nodes or src == dst:
                continue
            ed = GraphEdge(src=src, dst=dst, type=str(e.get("type", "related")),
                           weight=float(e.get("weight", 1.0)))
            self.edges.append(ed)
            self.adj[src].add(dst)
            self.adj[dst].add(src)
        # 3. 社区检测
        node_types = {nid: nd.type for nid, nd in self.nodes.items()}
        self.community_map = self.detector.detect(
            self.nodes.keys(),
            [(e.src, e.dst) for e in self.edges],
            node_types,
        )
        # 4. 生成社区报告
        self.communities = self._build_reports()
        return {
            "n_nodes": len(self.nodes),
            "n_edges": len(self.edges),
            "n_communities": len(self.communities),
        }

    def _build_reports(self) -> Dict[str, CommunityReport]:
        groups: Dict[str, List[str]] = defaultdict(list)
        for nid, cid in self.community_map.items():
            groups[cid].append(nid)
        reports: Dict[str, CommunityReport] = {}
        for cid, nids in groups.items():
            type_breakdown: Counter = Counter()
            all_tokens: Counter = Counter()
            labels: List[str] = []
            for nid in nids:
                nd = self.nodes[nid]
                type_breakdown[nd.type] += 1
                labels.append(nd.label)
                all_tokens.update(_tokenize(f"{nd.label} {nd.text}"))
            top_kw = [w for w, _ in all_tokens.most_common(12)]
            # 标题: 热门 type + 节点数
            main_type = type_breakdown.most_common(1)[0][0]
            title = f"社区 {cid}: {main_type} {type_breakdown[main_type]} 个 (总 {len(nids)})"
            # summary: type 分布 + top keywords + 代表节点名
            summary_lines = [
                f"节点: {len(nids)} 个, 类型分布: " + ", ".join(f"{t}×{c}" for t, c in type_breakdown.most_common()),
                f"高频 token: {', '.join(top_kw[:10])}",
                f"代表节点: {', '.join(labels[:8])}",
            ]
            reports[cid] = CommunityReport(
                id=cid, title=title, summary="\n".join(summary_lines),
                keywords=top_kw, node_ids=nids,
                type_breakdown=dict(type_breakdown),
            )
        return reports

    def stats(self) -> Dict[str, Any]:
        return {
            "n_nodes": len(self.nodes),
            "n_edges": len(self.edges),
            "n_communities": len(self.communities),
            "largest_community": max((len(r.node_ids) for r in self.communities.values()), default=0),
        }

    # ============ 查询 ============

    def query_local(self, question: str, max_entities: int = 3, hop: int = 1) -> Dict[str, Any]:
        q_tokens = set(_tokenize(question))
        if not q_tokens:
            return {"entities": [], "context": "", "hits": []}
        # 打分: label + text token 重叠
        scored: List[Tuple[float, str]] = []
        for nid, nd in self.nodes.items():
            n_tokens = set(_tokenize(f"{nd.label} {nd.text}"))
            if not n_tokens:
                continue
            overlap = len(q_tokens & n_tokens) / max(len(q_tokens), 1)
            if overlap > 0:
                scored.append((overlap, nid))
        scored.sort(key=lambda x: -x[0])
        hits = [nid for _, nid in scored[:max_entities]]
        if not hits:
            return {"entities": [], "context": "", "hits": []}
        # BFS 扩展
        visited: Set[str] = set(hits)
        frontier: Set[str] = set(hits)
        for _ in range(hop):
            nxt: Set[str] = set()
            for nid in frontier:
                nxt |= self.adj.get(nid, set())
            frontier = nxt - visited
            visited |= frontier
        # 拼接 context: 命中以 [HIT], 邻居 以 [NB]
        ctx_lines = []
        for nid in hits:
            nd = self.nodes[nid]
            ctx_lines.append(f"[HIT] {nd.type}:{nd.label} — {nd.text[:200]}")
        for nid in visited - set(hits):
            nd = self.nodes[nid]
            ctx_lines.append(f"[NB]  {nd.type}:{nd.label} — {nd.text[:120]}")
        return {
            "entities": [self.nodes[nid].to_dict() for nid in hits],
            "neighbors": [self.nodes[nid].to_dict() for nid in visited - set(hits)],
            "context": "\n".join(ctx_lines),
            "hits": hits,
        }

    def query_global(self, question: str, max_reports: int = 3) -> Dict[str, Any]:
        q_tokens = set(_tokenize(question))
        if not q_tokens or not self.communities:
            return {"reports": [], "context": ""}
        scored: List[Tuple[float, str]] = []
        for cid, rpt in self.communities.items():
            r_tokens = set(rpt.keywords)
            if not r_tokens:
                continue
            overlap = len(q_tokens & r_tokens) / max(len(q_tokens), 1)
            if overlap > 0:
                scored.append((overlap, cid))
        scored.sort(key=lambda x: -x[0])
        top_ids = [cid for _, cid in scored[:max_reports]]
        reports = [self.communities[cid] for cid in top_ids]
        ctx_lines = []
        for r in reports:
            ctx_lines.append(f"## {r.title}\n{r.summary}")
        return {
            "reports": [r.to_dict() for r in reports],
            "context": "\n\n".join(ctx_lines),
        }
