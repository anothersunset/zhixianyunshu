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
        String sourceSql = String.valueOf(ctx.state().getOrDefault("source_sql", ""));
        String pair = String.valueOf(ctx.state().getOrDefault("pair", "mysql->opengauss"));
        String[] dialects = pair.split("->", 2);
        String sourceDialect = dialects[0].trim();
        String targetDialect = dialects.length > 1 ? dialects[1].trim() : "postgresql";
        String prompt = """
            You are a SQL migration reviewer. Your task is to find errors in a %s-to-%s migration.

            === Source SQL (%s) ===
            %s

            === Generated Target SQL (%s) ===
            %s

            === Review Checklist (check EACH item) ===
            1. SYNTAX: Does the target SQL parse correctly as %s? Any source-dialect constructs, keywords, or operators remaining unconverted?
            2. FUNCTION CONVERSION: Is every source-dialect function correctly replaced? (e.g. DECODE->CASE, NVL->COALESCE, TO_CHAR->TO_CHAR with format review, CONNECT BY->WITH RECURSIVE)
            3. PAGINATION: If the source uses ROWNUM, was it correctly converted to simple LIMIT/OFFSET? ROW_NUMBER() OVER() combined with LIMIT is WRONG.
            4. HIERARCHY: If the source uses CONNECT BY, does the target have a complete WITH RECURSIVE CTE? Check: (a) is_leaf computed INSIDE the CTE as boolean, (b) LEVEL starts at 0, (c) anchor+recursive+JOIN structure complete?
            5. UPSERT: If the source uses MERGE INTO or ON DUPLICATE KEY, does the target use INSERT ... ON CONFLICT correctly with EXCLUDED.column?
            6. MISSING TRANSFORMATION: Did the generated SQL fail to convert any source-specific constructs?
            7. REGRESSIONS: Did the conversion introduce any new syntax errors or semantic problems?

            === Output Format (strictly follow) ===
            STATUS: CORRECT | NEEDS_FIX
            [If NEEDS_FIX, list each issue as:]
            ISSUE N: [checklist item number] LOCATION: [describe where]
            ERROR: [what is wrong]
            FIX: [exact correction needed]
            SUMMARY: [1-2 sentence overall assessment]
            """.formatted(sourceDialect, targetDialect,
                          sourceDialect, sourceSql,
                          targetDialect, patch,
                          targetDialect);
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("scripts", 18);
        if (llm.isReal()) {
            try {
                String reply = llm.reason(prompt);
                String upperReply = reply.toUpperCase();
                boolean needsCorrection = upperReply.contains("STATUS: NEEDS_FIX")
                    || upperReply.contains("NEEDS_FIX");
                // 额外检查：是否有编号的 ISSUE + ERROR 模式
                if (!needsCorrection) {
                    needsCorrection = upperReply.matches("(?s).*ISSUE\\s+\\d+.*ERROR:.*");
                }
                out.put("critique", reply);
                out.put("needs_correction", needsCorrection);
                out.put("critic_status", "ok");
                out.put("_confidence", 0.92);
                out.put("_real", true);
                out.put("_model", llm.providerName() + ":reasoner");
            } catch (Exception e) {
                // LLM 调用失败时，不谎报 CORRECT——那会让报告把"评审没跑成"显示成"评审通过"。
                // 如实标记 UNKNOWN + critic_status=error；不触发自纠正（没有真实评审意见的重生成
                // 只是白烧一次 LLM 调用，且可能越改越糟），把"评审未完成"这个事实透传给下游决策。
                out.put("critique", "STATUS: UNKNOWN\nDETAIL: Critic LLM 调用失败，本次未能完成评审（不触发自纠正）。");
                out.put("needs_correction", false);
                out.put("critic_status", "error");
                out.put("_confidence", 0.5);
                out.put("_real", true);
                out.put("_model", llm.providerName() + ":error");
            }
        } else {
            out.put("critique", "STATUS: CORRECT\nDETAIL: 补丁语法正确，AUTO_INCREMENT 转 SEQUENCE 正确。");
            out.put("needs_correction", false);
            out.put("critic_status", "mock");
            out.put("_confidence", 0.91);
            out.put("_real", false);
            out.put("_model", "mock");
        }
        return out;
    }
}
