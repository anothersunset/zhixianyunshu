"""
v2-step-13: GraphRAG community detector。

选 Louvain-Lite 而不引 networkx/igraph/graspologic, 原因:
  - 多一个 C 扩展依赖会拉高镜像体积 200MB+
  - CKG 场景下众多 small-scale 子图, 全面 Louvain 过重
  - Phase 3 要升级为真 Leiden 只需跳转 CommunityDetector 实现不动上层

算法:
1. 连通分量 (BFS) 得初始社区
2. 每个连通分量内如果节点 > limit, 按 node.type 制作 hub-spoke 折叠
3. 输出: {node_id: community_id}
"""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Dict, List, Set, Tuple, Iterable


class CommunityDetector:
    """轻量 community detector。

    Args:
        max_community_size: 单个 community 最多节点数, 超过在内部按 type 拆。
    """

    def __init__(self, max_community_size: int = 50):
        self.max_community_size = max_community_size

    def detect(self, node_ids: Iterable[str], edges: List[Tuple[str, str]],
               node_types: Dict[str, str]) -> Dict[str, str]:
        """返回映射 node_id -> community_id。社区以 c-N 命名。"""
        node_set: Set[str] = set(node_ids)
        # 邻接表
        adj: Dict[str, Set[str]] = defaultdict(set)
        for u, v in edges:
            if u in node_set and v in node_set and u != v:
                adj[u].add(v)
                adj[v].add(u)
        # 连通分量
        visited: Set[str] = set()
        components: List[List[str]] = []
        for n in node_set:
            if n in visited:
                continue
            comp: List[str] = []
            dq = deque([n])
            visited.add(n)
            while dq:
                cur = dq.popleft()
                comp.append(cur)
                for nb in adj.get(cur, ()):
                    if nb not in visited:
                        visited.add(nb)
                        dq.append(nb)
            components.append(comp)
        # 折叠超限 component
        comm_map: Dict[str, str] = {}
        next_cid = 0
        for comp in components:
            if len(comp) <= self.max_community_size:
                cid = f"c-{next_cid}"
                next_cid += 1
                for n in comp:
                    comm_map[n] = cid
            else:
                # 按 type 分组, 每组一个 community
                groups: Dict[str, List[str]] = defaultdict(list)
                for n in comp:
                    groups[node_types.get(n, "unknown")].append(n)
                for tp, nodes in groups.items():
                    cid = f"c-{next_cid}"
                    next_cid += 1
                    for n in nodes:
                        comm_map[n] = cid
        return comm_map
