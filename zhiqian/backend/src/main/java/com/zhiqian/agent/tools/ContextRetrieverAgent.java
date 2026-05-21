package com.zhiqian.agent.tools;

import com.zhiqian.agent.AgentContext;
import com.zhiqian.agent.AgentTool;
import com.zhiqian.llm.LlmClient;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Stage 02 — 上下文检索。
 * v2-step-03 使用 in-memory 文档库 + 启发式打分。
 * v2-step-05 会替换为 Qdrant + BGE-M3 混合检索。
 */
public class ContextRetrieverAgent implements AgentTool {
    private final LlmClient llm;
    public ContextRetrieverAgent(LlmClient llm) { this.llm = llm; }
    @Override public String name() { return "Context Retriever"; }
    @Override public String description() { return "从知识库混合检索迁移上下文文档"; }
    @Override public Map<String, Object> run(AgentContext ctx, Map<String, Object> input) {
        // 本步 mock 一份检索结果，后续 step 4-5 接入 Qdrant + BGE-M3。
        List<Map<String, Object>> docs = List.of(
            Map.of("id", "og-spec-08", "score", 0.91, "title", "openGauss 序列与自增字段语法"),
            Map.of("id", "og-spec-12", "score", 0.87, "title", "时间类型默认值差异"),
            Map.of("id", "og-spec-19", "score", 0.82, "title", "JSON / JSONB 存储与查询"),
            Map.of("id", "og-spec-23", "score", 0.78, "title", "事务隔离级别与 MVCC"),
            Map.of("id", "og-spec-31", "score", 0.75, "title", "存储过程与触发器改写")
        );
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("top_k", 50);
        out.put("top_n", docs.size());
        out.put("retrieved", docs);
        out.put("_confidence", 0.78);
        out.put("_model", llm.isReal() ? "bge-m3-pending" : "mock-retriever");
        out.put("_real", false);
        return out;
    }
}
