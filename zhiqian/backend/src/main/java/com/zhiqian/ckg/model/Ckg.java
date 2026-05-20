package com.zhiqian.ckg.model;

import org.jgrapht.graph.DefaultDirectedGraph;

import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

public class Ckg {
    private final DefaultDirectedGraph<CkgNode, CkgEdge> graph =
        new DefaultDirectedGraph<>(CkgEdge.class);
    private final Map<String, CkgNode> byId = new HashMap<>();
    private final Map<String, List<CkgNode>> byKind = new HashMap<>();

    public CkgNode addNode(CkgNode n) {
        if (byId.containsKey(n.id())) return byId.get(n.id());
        byId.put(n.id(), n);
        byKind.computeIfAbsent(n.kind(), k -> new ArrayList<>()).add(n);
        graph.addVertex(n);
        return n;
    }

    public CkgNode addNode(String id, String kind, Map<String, Object> attrs) {
        return addNode(new CkgNode(id, kind, attrs));
    }

    public CkgEdge addEdge(CkgNode src, CkgNode dst, String relation) {
        return addEdge(src, dst, relation, null);
    }

    public CkgEdge addEdge(CkgNode src, CkgNode dst, String relation, Map<String, Object> attrs) {
        if (src == null || dst == null) return null;
        graph.addVertex(src);
        graph.addVertex(dst);
        CkgEdge e = new CkgEdge(relation, attrs);
        graph.addEdge(src, dst, e);
        return e;
    }

    public CkgNode getById(String id) { return byId.get(id); }

    public List<CkgNode> nodes(String kind) {
        return byKind.getOrDefault(kind, List.of());
    }

    public Collection<CkgNode> allNodes() { return byId.values(); }

    public int countByKind(String kind) { return nodes(kind).size(); }

    public List<CkgNode> neighbors(CkgNode n, String relation) {
        if (!graph.containsVertex(n)) return List.of();
        return graph.outgoingEdgesOf(n).stream()
            .filter(e -> relation == null || relation.equals(e.relation()))
            .map(graph::getEdgeTarget)
            .collect(Collectors.toList());
    }

    public DefaultDirectedGraph<CkgNode, CkgEdge> raw() { return graph; }

    public Map<String, Integer> kindHistogram() {
        Map<String, Integer> m = new HashMap<>();
        byKind.forEach((k, v) -> m.put(k, v.size()));
        return m;
    }
}
