package com.zhiqian.agent.tools;

import com.zhiqian.agent.AgentContext;
import com.zhiqian.agent.AgentTool;
import com.zhiqian.llm.LlmClient;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Stage 04 — 生成 SQL 补丁。v2-step-09 会接入 sqlglot AST 转译，本步仅 LLM 改写。
 */
public class SqlPatcherAgent implements AgentTool {
    private final LlmClient llm;
    public SqlPatcherAgent(LlmClient llm) { this.llm = llm; }
    @Override public String name() { return "SQL Patcher"; }
    @Override public String description() { return "生成可应用的 SQL 补丁 diff"; }
    @Override public Map<String, Object> run(AgentContext ctx, Map<String, Object> input) {
        Object reasoning = input.getOrDefault("reasoning", "");
        String prompt = "根据以下修改思路，输出 MySQL→openGauss 补丁的示例（仅输出代码块，不要解释）：\n\n" + reasoning;
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("patches", 12);
        out.put("review_required", 2);
        if (llm.isReal()) {
            String reply = llm.chat(prompt);
            out.put("patch_preview", reply);
            out.put("_confidence", 0.89);
            out.put("_real", true);
        } else {
            out.put("patch_preview", "```sql\n-- before (MySQL)\nCREATE TABLE orders (id INT AUTO_INCREMENT PRIMARY KEY, ...);\n-- after  (openGauss)\nCREATE SEQUENCE orders_id_seq;\nCREATE TABLE orders (id INT DEFAULT nextval('orders_id_seq') PRIMARY KEY, ...);\n```");
            out.put("_confidence", 0.88);
            out.put("_real", false);
        }
        out.put("_model", llm.providerName());
        return out;
    }
}
