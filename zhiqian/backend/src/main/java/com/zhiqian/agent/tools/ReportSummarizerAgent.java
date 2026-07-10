package com.zhiqian.agent.tools;

import com.zhiqian.agent.AgentContext;
import com.zhiqian.agent.AgentTool;
import com.zhiqian.llm.LlmClient;

import java.util.LinkedHashMap;
import java.util.Map;

/** Stage 06: produce a Markdown report from the actual task context. */
public class ReportSummarizerAgent implements AgentTool {
    private final LlmClient llm;

    public ReportSummarizerAgent(LlmClient llm) {
        this.llm = llm;
    }

    @Override
    public String name() {
        return "Report Summarizer";
    }

    @Override
    public String description() {
        return "Generate the persisted migration report";
    }

    @Override
    public Map<String, Object> run(AgentContext ctx, Map<String, Object> input) {
        Object summary = input.getOrDefault("summary", "");
        Object critique = input.getOrDefault("critique", "");
        String sourceSql = String.valueOf(ctx.state().getOrDefault("source_sql", ""));
        String targetSql = String.valueOf(ctx.state().getOrDefault("patch_preview", ""));
        String pair = String.valueOf(ctx.state().getOrDefault("pair", "mysql->opengauss"));
        String prompt = "Generate a Chinese Markdown SQL migration report with overview, risks, "
            + "changes and validation recommendations. Use only the supplied task data.\n\n"
            + "Dialect pair: " + pair + "\n\n"
            + "Source SQL:\n" + sourceSql + "\n\n"
            + "Target SQL:\n" + targetSql + "\n\n"
            + "Analysis:\n" + summary + "\n\n"
            + "Review:\n" + critique;

        Map<String, Object> output = new LinkedHashMap<>();
        output.put("report_url", "/api/tasks/" + ctx.taskId() + "/report/download");
        if (llm.isReal()) {
            output.put("report_md", llm.chat(prompt));
            output.put("_confidence", 0.94);
            output.put("_real", true);
        } else {
            output.put("report_md", "# Migration report\n\n"
                + "## Dialect pair\n" + pair + "\n\n"
                + "## Source SQL\n```sql\n" + sourceSql + "\n```\n\n"
                + "## Target SQL\n" + targetSql + "\n\n"
                + "## Analysis\n" + summary + "\n\n"
                + "## Review\n" + critique + "\n");
            output.put("_confidence", 0.75);
            output.put("_real", false);
        }
        output.put("_model", llm.providerName());
        return output;
    }
}
