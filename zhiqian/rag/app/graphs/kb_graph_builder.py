"""从 KB 文档提取 GraphRAG 实体与关系。

v2-step-14: 边生成优化 — 技术 token 提取、same_source top-K 限制、
跨类型桥接语义评分、全局关键词重叠 + per-node cap。
"""
from __future__ import annotations
import re
from collections import defaultdict
from typing import Any, Dict, List, Set

# doc ID 前缀 → 实体类型
_PREFIX_TYPE = {
    "kb-func-": "Function",
    "kb-syntax-": "Syntax",
    "kb-type-": "TypeMapping",
    "kb-config-": "Config",
    "kb-dep-": "Dependency",
    "kb-join-": "Join",
}

def _doc_type(doc_id: str) -> str:
    for prefix, t in _PREFIX_TYPE.items():
        if doc_id.startswith(prefix):
            return t
    return "Unknown"


# 跨类型关联规则：哪些类型在迁移中是相关的
_TYPE_BRIDGE = {
    ("Function", "Function"): 0.6,
    ("Function", "Syntax"): 0.4,
    ("Function", "TypeMapping"): 0.3,
    ("Syntax", "Syntax"): 0.5,
    ("Syntax", "TypeMapping"): 0.4,
    ("Syntax", "Join"): 0.5,
    ("TypeMapping", "TypeMapping"): 0.5,
    ("Config", "Config"): 0.5,
    ("Config", "Dependency"): 0.6,
    # v2-step-14: 补充缺失的类型桥接
    ("Join", "Function"): 0.4,
    ("Config", "TypeMapping"): 0.3,
}

# v2-step-14: SQL 技术术语 + 中文词（>=2 字符）
_TOKEN_RE = re.compile(r"[A-Z_][A-Z0-9_]{2,}|[\u4e00-\u9fff]{2,}")


def _extract_tokens(text: str) -> Set[str]:
    """提取技术 token（SQL 关键词 + 中文词组）。"""
    return {t.lower() for t in _TOKEN_RE.findall(text or "")}


def _add_scored_edges(
    edges: list, scored_pairs: List[tuple], max_per_node: int, edge_type: str,
):
    """通用：从得分排序的节点对中添加边，每节点最多 max_per_node 条。"""
    per_doc_count: Dict[str, int] = defaultdict(int)
    for overlap, src, dst in scored_pairs:
        if per_doc_count[src] >= max_per_node or per_doc_count[dst] >= max_per_node:
            continue
        weight = min(overlap * 0.15, 0.6)
        edges.append({"src": src, "dst": dst, "type": edge_type, "weight": weight})
        per_doc_count[src] += 1
        per_doc_count[dst] += 1


def build_graph_from_docs(docs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """从 KB 文档列表生成 GraphRAG 的 nodes + edges。

    v2-step-14 优化：
    - 技术 token 提取（SQL 术语 + 中文词）
    - same_source 从全连接 → top-K token-overlap
    - 跨类型桥接用 token 重叠排序而非任意 top-5
    - 关键词重叠从滑动窗口 → 全局 all-pairs + per-node cap
    """
    nodes = []
    for d in docs:
        doc_id = d["id"]
        text = d.get("text", "")
        label = doc_id.replace("kb-", "").replace("-", " ").title()
        nodes.append({
            "id": doc_id,
            "type": _doc_type(doc_id),
            "label": label,
            "text": text[:300],
        })

    # ── 预计算每个节点的 token 集合（供后续所有步骤复用）──
    node_tokens: Dict[str, Set[str]] = {
        n["id"]: _extract_tokens(n["text"] + " " + n.get("label", ""))
        for n in nodes
    }

    edges: List[dict] = []

    # ── 1) 同源文件 top-K token-overlap 连接 ──
    by_source = defaultdict(list)
    for d in docs:
        src_file = d.get("source", "").split("#")[0] if d.get("source") else ""
        if src_file:
            by_source[src_file].append(d["id"])

    for src_file, doc_ids in by_source.items():
        n = len(doc_ids)
        if n <= 3:
            # 小源文件：保持全连接
            for i in range(n):
                for j in range(i + 1, n):
                    edges.append({
                        "src": doc_ids[i], "dst": doc_ids[j],
                        "type": "same_source", "weight": 0.5,
                    })
        else:
            # 大源文件：每 doc 取 top-3 token 重叠最高的邻居
            scored = []
            for i in range(n):
                ti = node_tokens.get(doc_ids[i], set())
                if not ti:
                    continue
                for j in range(i + 1, n):
                    tj = node_tokens.get(doc_ids[j], set())
                    overlap = len(ti & tj)
                    if overlap >= 1:
                        scored.append((overlap, doc_ids[i], doc_ids[j]))
            scored.sort(key=lambda x: -x[0])
            _add_scored_edges(edges, scored, max_per_node=3, edge_type="same_source")

    # ── 2) 跨类型桥接：语义评分取 top-5 ──
    type_idx = defaultdict(list)
    for n in nodes:
        type_idx[n["type"]].append(n["id"])

    for (t1, t2), weight in _TYPE_BRIDGE.items():
        ids1 = type_idx.get(t1, [])
        ids2 = type_idx.get(t2, [])
        if not ids1 or not ids2:
            continue
        scored = []
        for n1 in ids1:
            t1_tokens = node_tokens.get(n1, set())
            if not t1_tokens:
                continue
            for n2 in ids2:
                if n1 == n2:
                    continue
                t2_tokens = node_tokens.get(n2, set())
                overlap = len(t1_tokens & t2_tokens)
                if overlap >= 1:
                    scored.append((overlap, n1, n2))
        scored.sort(key=lambda x: -x[0])
        for _, n1, n2 in scored[:5]:
            edges.append({
                "src": n1, "dst": n2,
                "type": f"{t1}-{t2}", "weight": weight,
            })

    # ── 3) 关键词重叠：全局 all-pairs + 每节点 top-8 ──
    all_scored = []
    for i in range(len(nodes)):
        ti = node_tokens.get(nodes[i]["id"], set())
        if not ti:
            continue
        for j in range(i + 1, len(nodes)):
            tj = node_tokens.get(nodes[j]["id"], set())
            overlap = len(ti & tj)
            if overlap >= 2:
                all_scored.append((overlap, nodes[i]["id"], nodes[j]["id"]))
    all_scored.sort(key=lambda x: -x[0])
    _add_scored_edges(edges, all_scored, max_per_node=8, edge_type="keyword_overlap")

    # ── 去重 ──
    seen = set()
    unique_edges = []
    for e in edges:
        key = tuple(sorted([e["src"], e["dst"]]))
        if key not in seen:
            seen.add(key)
            unique_edges.append(e)

    return {"nodes": nodes, "edges": unique_edges}
