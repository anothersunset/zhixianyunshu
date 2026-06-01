package com.zhiqian.temporal.workflow;

import com.zhiqian.agent.AgentContext;
import com.zhiqian.agent.AgentTool;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import java.util.Map;

/**
 * v2-step-14: Activity 实现。仅在 Temporal 启用时装载。
 */
@Slf4j
@Component
@ConditionalOnProperty(name = "app.temporal.enabled", havingValue = "true")
public class MigrationActivitiesImpl implements MigrationActivities {

    private final ObjectProvider<AgentTool> schemaAnalyzer;
    private final ObjectProvider<AgentTool> contextRetriever;
    private final ObjectProvider<AgentTool> sqlReasoner;
    private final ObjectProvider<AgentTool> sqlPatcher;
    private final ObjectProvider<AgentTool> sqlCritic;
    private final ObjectProvider<AgentTool> reportSummarizer;

    public MigrationActivitiesImpl(
            @Qualifier("schemaAnalyzerAgent")    ObjectProvider<AgentTool> schemaAnalyzer,
            @Qualifier("contextRetrieverAgent")  ObjectProvider<AgentTool> contextRetriever,
            @Qualifier("sqlReasonerAgent")       ObjectProvider<AgentTool> sqlReasoner,
            @Qualifier("sqlPatcherAgent")        ObjectProvider<AgentTool> sqlPatcher,
            @Qualifier("sqlCriticAgent")         ObjectProvider<AgentTool> sqlCritic,
            @Qualifier("reportSummarizerAgent")  ObjectProvider<AgentTool> reportSummarizer) {
        this.schemaAnalyzer = schemaAnalyzer;
        this.contextRetriever = contextRetriever;
        this.sqlReasoner = sqlReasoner;
        this.sqlPatcher = sqlPatcher;
        this.sqlCritic = sqlCritic;
        this.reportSummarizer = reportSummarizer;
    }

    @Override public Map<String, Object> runSchemaAnalyzer(Map<String, Object> ctx)    { return run("SCHEMA",   schemaAnalyzer.getObject(),    ctx); }
    @Override public Map<String, Object> runContextRetriever(Map<String, Object> ctx)  { return run("RETRIEVE", contextRetriever.getObject(),  ctx); }
    @Override public Map<String, Object> runSqlReasoner(Map<String, Object> ctx)       { return run("REASON",   sqlReasoner.getObject(),       ctx); }
    @Override public Map<String, Object> runSqlPatcher(Map<String, Object> ctx)        { return run("PATCH",    sqlPatcher.getObject(),        ctx); }
    @Override public Map<String, Object> runSqlCritic(Map<String, Object> ctx)         { return run("CRITIC",   sqlCritic.getObject(),         ctx); }
    @Override public Map<String, Object> runReportSummarizer(Map<String, Object> ctx)  { return run("REPORT",   reportSummarizer.getObject(),  ctx); }

    private Map<String, Object> run(String stage, AgentTool tool, Map<String, Object> ctx) {
        long t0 = System.currentTimeMillis();
        AgentContext agentCtx = new AgentContext(asLong(ctx.get("taskId")), asLong(ctx.get("projectId")));
        try {
            Map<String, Object> out = tool.run(agentCtx, ctx);
            out.putIfAbsent("_ok", true);
            out.putIfAbsent("_elapsedMs", System.currentTimeMillis() - t0);
            log.info("[temporal-activity] {} ok in {}ms", stage, System.currentTimeMillis() - t0);
            return out;
        } catch (Exception e) {
            log.warn("[temporal-activity] {} failed: {}", stage, e.getMessage());
            // Temporal 会按 RetryOptions 重试; 为了让 workflow 可见, 招出运行时异常
            throw new RuntimeException("Stage " + stage + " failed: " + e.getMessage(), e);
        }
    }

    private long asLong(Object v) {
        if (v == null) return 0L;
        if (v instanceof Number n) return n.longValue();
        try { return Long.parseLong(v.toString()); } catch (Exception ignored) { return 0L; }
    }
}
