package com.zhiqian.temporal.workflow;

import com.zhiqian.agent.AgentContext;
import com.zhiqian.agent.AgentRunner;
import com.zhiqian.agent.AgentTool;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;
import java.util.Map;

/**
 * v2-step-14: Activity 实现。Spring bean, 依赖现有 AgentRunner。
 *
 * <p>不重复逻辑: 每个 activity 只是“查找同名 AgentTool bean + 调 runner.run”。
 * 这样 Temporal/AgentRunner 两路径走同一套 Agent 代码, 避免双护。
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class MigrationActivitiesImpl implements MigrationActivities {

    private final AgentRunner runner;
    @Qualifier("schemaAnalyzerAgent")    private final AgentTool schemaAnalyzer;
    @Qualifier("contextRetrieverAgent")  private final AgentTool contextRetriever;
    @Qualifier("sqlReasonerAgent")       private final AgentTool sqlReasoner;
    @Qualifier("sqlPatcherAgent")        private final AgentTool sqlPatcher;
    @Qualifier("sqlCriticAgent")         private final AgentTool sqlCritic;
    @Qualifier("reportSummarizerAgent")  private final AgentTool reportSummarizer;

    @Override public Map<String, Object> runSchemaAnalyzer(Map<String, Object> ctx)    { return run("SCHEMA",   schemaAnalyzer,    ctx); }
    @Override public Map<String, Object> runContextRetriever(Map<String, Object> ctx)  { return run("RETRIEVE", contextRetriever,  ctx); }
    @Override public Map<String, Object> runSqlReasoner(Map<String, Object> ctx)       { return run("REASON",   sqlReasoner,       ctx); }
    @Override public Map<String, Object> runSqlPatcher(Map<String, Object> ctx)        { return run("PATCH",    sqlPatcher,        ctx); }
    @Override public Map<String, Object> runSqlCritic(Map<String, Object> ctx)         { return run("CRITIC",   sqlCritic,         ctx); }
    @Override public Map<String, Object> runReportSummarizer(Map<String, Object> ctx)  { return run("REPORT",   reportSummarizer,  ctx); }

    private Map<String, Object> run(String stage, AgentTool tool, Map<String, Object> ctx) {
        long t0 = System.currentTimeMillis();
        AgentContext agentCtx = AgentContext.builder()
                .taskId(asLong(ctx.get("taskId")))
                .projectId(asLong(ctx.get("projectId")))
                .stage(stage)
                .build();
        try {
            Map<String, Object> out = runner.run(tool, agentCtx, ctx);
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
