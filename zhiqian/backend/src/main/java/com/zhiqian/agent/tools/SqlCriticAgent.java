package com.zhiqian.agent.tools;

import com.zhiqian.agent.AgentContext;
import com.zhiqian.agent.AgentTool;
import com.zhiqian.llm.LlmClient;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Stage 05 — 补丁评审。使用 reasoner-model 判别修改是否合理。
 */
public class SqlCriticAgent implements AgentTool {
    private final LlmClient llm;
    public SqlCriticAgent(LlmClient llm) { this.llm = llm; }
    @Override public String name() { return "SQL Critic"; }
    @Override public String description() { return "反思与评审补丁正确性"; }
    @Override public Map<String, Object> run(AgentContext ctx, Map<String, Object> input) {
        Object patch = input.getOrDefault("patch_preview", "");
        String prompt = "评审以下 SQL 补丁，指出 1-2 个要人工复查的点（中文、简短）：\n\n" + patch;
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("scripts", 18);
        if (llm.isReal()) {
            String reply = llm.reason(prompt);
            out.put("critique", reply);
            out.put("_confidence", 0.92);
            out.put("_real", true);
            out.put("_model", llm.providerName() + ":reasoner");
        } else {
            out.put("critique", "补丁语法正确。需要人工复查：\n1. orders_id_seq 是否与原表初始最大值保持一致\n2. JSON 转 JSONB 后是否需保留原始字段顺序");
            out.put("_confidence", 0.91);
            out.put("_real", false);
            out.put("_model", "mock");
        }
        return out;
    }
}
