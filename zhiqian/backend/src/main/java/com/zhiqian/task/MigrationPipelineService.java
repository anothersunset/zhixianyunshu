package com.zhiqian.task;

import com.zhiqian.agent.AgentContext;
import com.zhiqian.agent.AgentGraph;
import com.zhiqian.agent.AgentRunner;
import com.zhiqian.agent.AgentStep;
import com.zhiqian.agent.tools.ContextRetrieverAgent;
import com.zhiqian.agent.tools.FeatureScannerAgent;
import com.zhiqian.agent.tools.ReportSummarizerAgent;
import com.zhiqian.agent.tools.SchemaAnalyzerAgent;
import com.zhiqian.agent.tools.SqlCriticAgent;
import com.zhiqian.agent.tools.SqlPatcherAgent;
import com.zhiqian.agent.tools.SqlReasonerAgent;
import com.zhiqian.llm.LlmClient;
import com.zhiqian.observability.LangfuseClient;
import com.zhiqian.observability.TraceHandle;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.function.Consumer;

@Service
@RequiredArgsConstructor
public class MigrationPipelineService {
    private static final int MAX_REFINE_ROUNDS = 1;

    private final LlmClient llm;
    private final AgentRunner runner;
    private final LangfuseClient langfuse;

    @Value("${app.rag.base-url:http://localhost:8001}")
    private String ragUrl;

    public PipelineResult execute(MigrationInput input, Consumer<AgentStep> listener) {
        AgentContext context = new AgentContext(input.taskId(), input.projectId());
        context.state().put("source_sql", input.sourceSql());
        context.state().put("pair", input.sourceDialect() + "->" + input.targetDialect());
        context.state().put("sourceDialect", input.sourceDialect());
        context.state().put("targetDialect", input.targetDialect());
        context.state().put("retrieval", input.retrievalMode());
        // Keep the visible pipeline at six business agents while running the
        // deterministic dialect scan as zero-cost preprocessing.  UNKNOWN
        // features then survive into the trace and terminal review status.
        context.state().putAll(new FeatureScannerAgent().run(context, Map.of()));

        TraceHandle trace = langfuse.newTrace(
            "task.migration",
            Map.of("taskId", input.taskId(), "projectId", input.projectId()),
            Map.of("llm_provider", llm.providerName(), "llm_real", llm.isReal(), "agents", 6),
            List.of("backend", "migration", "task-" + input.taskId())
        );

        List<AgentStep> steps = new ArrayList<>();
        runner.run(buildGraph(), context, step -> {
            steps.add(step);
            listener.accept(step);
        }, trace);

        AgentStep failedStep = steps.stream().filter(step -> "FAIL".equals(step.status())).findFirst().orElse(null);
        boolean reviewRequired = Boolean.TRUE.equals(context.state().get("needs_correction"))
            || "error".equals(context.state().get("critic_status"))
            || (context.state().get("unknown_feature_count") instanceof Number count
                && count.intValue() > 0);
        String resultSql = stripFence(String.valueOf(context.state().getOrDefault("patch_preview", "")));
        String reportMd = String.valueOf(context.state().getOrDefault("report_md", ""));

        String status = failedStep != null ? "FAILED" : reviewRequired ? "REVIEW_REQUIRED" : "DONE";
        trace.finish(
            Map.of("status", status, "stages_executed", steps.size()),
            Map.of("task_done", failedStep == null && !reviewRequired)
        );
        return new PipelineResult(
            status,
            resultSql,
            reportMd,
            failedStep == null ? null : failedStep.stage(),
            reviewRequired,
            context.state(),
            steps,
            trace.isNoop() ? null : trace.getTraceId()
        );
    }

    private AgentGraph buildGraph() {
        AgentGraph graph = new AgentGraph();
        graph.addNode("01-analyzer", new SchemaAnalyzerAgent(llm));
        graph.addNode("02-retriever", new ContextRetrieverAgent(llm, ragUrl));
        graph.addNode("03-reasoner", new SqlReasonerAgent(llm));
        graph.addNode("04-patcher", new SqlPatcherAgent(llm));
        graph.addNode("05-critic", new SqlCriticAgent(llm));
        graph.addNode("06-reporter", new ReportSummarizerAgent(llm));
        graph.addEdge("01-analyzer", ctx -> "02-retriever");
        graph.addEdge("02-retriever", ctx -> "03-reasoner");
        graph.addEdge("03-reasoner", ctx -> "04-patcher");
        graph.addEdge("04-patcher", ctx -> "05-critic");
        graph.addEdge("05-critic", ctx -> {
            boolean needsFix = Boolean.TRUE.equals(ctx.state().get("needs_correction"));
            int round = ctx.state().get("refine_round") instanceof Number n ? n.intValue() : 0;
            if (needsFix && round < MAX_REFINE_ROUNDS) {
                ctx.state().put("refine_round", round + 1);
                return "04-patcher";
            }
            return "06-reporter";
        });
        graph.addEdge("06-reporter", ctx -> null);
        graph.entry("01-analyzer");
        return graph;
    }

    static String stripFence(String value) {
        String sql = value == null ? "" : value.trim();
        if (sql.startsWith("```")) {
            sql = sql.replaceFirst("^```(?:sql)?\\s*", "");
            sql = sql.replaceFirst("\\s*```$", "");
        }
        return sql.trim();
    }

    public record MigrationInput(
        Long taskId,
        Long projectId,
        String sourceSql,
        String sourceDialect,
        String targetDialect,
        String retrievalMode
    ) {}

    public record PipelineResult(
        String status,
        String resultSql,
        String reportMd,
        String failedStage,
        boolean reviewRequired,
        Map<String, Object> state,
        List<AgentStep> steps,
        String traceId
    ) {}
}
