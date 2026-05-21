package com.zhiqian.ckg;

import com.zhiqian.common.Result;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * v2-step-16: CKG 图谱 REST 接口, 供前端 Cytoscape.js 渲染。
 * 当前返回 demo 图 (13 节点 + 10 边), 后续接入 CkgAnalyzerService 后读取项目真实分析结果。
 */
@RestController
@RequestMapping("/api/ckg")
public class CkgGraphController {

    @GetMapping("/graph")
    public Result<Map<String, Object>> graph(@RequestParam(name = "projectId", defaultValue = "1") Long projectId) {
        Map<String, Object> resp = new HashMap<>();
        resp.put("projectId", projectId);
        resp.put("demo", true);
        resp.put("nodes", demoNodes());
        resp.put("edges", demoEdges());
        Map<String, Integer> stats = new HashMap<>();
        stats.put("files", 1);
        stats.put("classes", 2);
        stats.put("methods", 4);
        stats.put("tables", 3);
        stats.put("columns", 3);
        resp.put("stats", stats);
        return Result.ok(resp);
    }

    private List<Map<String, Object>> demoNodes() {
        List<Map<String, Object>> nodes = new ArrayList<>();
        nodes.add(node("f1", "OrderService.java", "File"));
        nodes.add(node("c1", "OrderService", "Class"));
        nodes.add(node("c2", "OrderRepository", "Class"));
        nodes.add(node("m1", "createOrder", "Method"));
        nodes.add(node("m2", "findById", "Method"));
        nodes.add(node("m3", "updateStatus", "Method"));
        nodes.add(node("m4", "save", "Method"));
        nodes.add(node("t1", "orders", "Table"));
        nodes.add(node("t2", "order_items", "Table"));
        nodes.add(node("t3", "users", "Table"));
        nodes.add(node("col1", "orders.id", "Column"));
        nodes.add(node("col2", "orders.user_id", "Column"));
        nodes.add(node("col3", "orders.status", "Column"));
        return nodes;
    }

    private List<Map<String, Object>> demoEdges() {
        List<Map<String, Object>> edges = new ArrayList<>();
        edges.add(edge("e1", "f1", "c1", "contains"));
        edges.add(edge("e2", "c1", "m1", "has_method"));
        edges.add(edge("e3", "c1", "m3", "has_method"));
        edges.add(edge("e4", "c2", "m2", "has_method"));
        edges.add(edge("e5", "c2", "m4", "has_method"));
        edges.add(edge("e6", "m1", "m4", "calls"));
        edges.add(edge("e7", "m1", "t1", "uses_table"));
        edges.add(edge("e8", "m2", "t1", "reads"));
        edges.add(edge("e9", "t1", "col1", "has_column"));
        edges.add(edge("e10", "t1", "col2", "has_column"));
        return edges;
    }

    private static Map<String, Object> node(String id, String label, String type) {
        Map<String, Object> n = new HashMap<>();
        n.put("id", id);
        n.put("label", label);
        n.put("type", type);
        return n;
    }

    private static Map<String, Object> edge(String id, String source, String target, String type) {
        Map<String, Object> e = new HashMap<>();
        e.put("id", id);
        e.put("source", source);
        e.put("target", target);
        e.put("type", type);
        return e;
    }
}
