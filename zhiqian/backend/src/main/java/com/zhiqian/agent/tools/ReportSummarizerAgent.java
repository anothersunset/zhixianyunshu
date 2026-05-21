package com.zhiqian.agent.tools;

import com.zhiqian.agent.AgentContext;
import com.zhiqian.agent.AgentTool;
import com.zhiqian.llm.LlmClient;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Stage 06 — 报告总结。输出迁移报告 markdown。
 */
public class ReportSummarizerAgent implements AgentTool {
    private final LlmClient llm;
    public ReportSummarizerAgent(LlmClient llm) { this.llm = llm; }
    @Override public String name() { return "Report Summarizer"; }
    @Override public String description() { return "输出交付物：迁移报告 markdown"; }
    @Override public Map<String, Object> run(AgentContext ctx, Map<String, Object> input) {
        Object summary = input.getOrDefault("summary", "");
        Object critique = input.getOrDefault("critique", "");
        String prompt = "生成一份迁移报告（markdown，中文，含概述/风险/修改/验证建议四节）：\n\n风险总结：" + summary + "\n\n评审意见：" + critique;
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("report_url", "/api/reports/task-" + ctx.taskId() + ".md");
        if (llm.isReal()) {
            String reply = llm.chat(prompt);
            out.put("report_md", reply);
            out.put("_confidence", 0.94);
            out.put("_real", true);
        } else {
            out.put("report_md", "# 迁移报告\n## 概述\n本次从 MySQL 到 openGauss 的迁移覆盖 312 个文件、共 78 条 SQL。\n\n## 风险\nAUTO_INCREMENT / DATETIME / JSON 三类不兼容点。\n\n## 修改\n生成 12 份补丁，2 份需人工复查。\n\n## 验证建议\n18 脚本全量回庒。");
            out.put("_confidence", 0.93);
            out.put("_real", false);
        }
        out.put("_model", llm.providerName());
        return out;
    }
}
