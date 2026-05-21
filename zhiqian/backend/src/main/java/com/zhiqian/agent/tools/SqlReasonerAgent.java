package com.zhiqian.agent.tools;

import com.zhiqian.agent.AgentContext;
import com.zhiqian.agent.AgentTool;
import com.zhiqian.llm.LlmClient;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Stage 03 — 推理。使用 reasoner-model（R1 类）输出修改思路。
 */
public class SqlReasonerAgent implements AgentTool {
    private final LlmClient llm;
    public SqlReasonerAgent(LlmClient llm) { this.llm = llm; }
    @Override public String name() { return "SQL Reasoner"; }
    @Override public String description() { return "结合检索上下文推理 SQL 改写思路"; }
    @Override public Map<String, Object> run(AgentContext ctx, Map<String, Object> input) {
        Object summary = input.getOrDefault("summary", "");
        String prompt = "你是高级 DBA。基于以下迁移风险总结，生成 3 条具体可执行的修改思路（中文，一句一条）：\n\n" + summary;
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("risk_units", 14);
        if (llm.isReal()) {
            String reply = llm.reason(prompt);
            out.put("reasoning", reply);
            out.put("_confidence", 0.84);
            out.put("_real", true);
            out.put("_model", llm.providerName() + ":reasoner");
        } else {
            out.put("reasoning", "1. AUTO_INCREMENT → CREATE SEQUENCE + DEFAULT nextval\n2. DATETIME DEFAULT CURRENT_TIMESTAMP → TIMESTAMP DEFAULT now()\n3. JSON → JSONB + GIN 索引");
            out.put("strategies", List.of("sequence-rewrite", "timestamp-default-fix", "jsonb-migration"));
            out.put("_confidence", 0.81);
            out.put("_real", false);
            out.put("_model", "mock");
        }
        return out;
    }
}
