package com.zhiqian.temporal.workflow;

import io.temporal.activity.ActivityOptions;
import io.temporal.common.RetryOptions;
import io.temporal.workflow.Workflow;
import java.time.Duration;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * v2-step-14: MigrationWorkflow 实现。
 *
 * <p>指定。节点顺序: schema → retrieve → reason → patch → critic → report。
 * 每节点动一个 activity, 本地 startToClose 10 min, 重试 3 次。
 * 节点间使用 ctx 顺传, 上一节点输出是下一节点输入的一部分。
 *
 * <p>重试策略: 允许 LLM 网络抖动 / 限流临时失败, 指数退避。
 */
public class MigrationWorkflowImpl implements MigrationWorkflow {

    private static final ActivityOptions DEFAULT_OPTIONS = ActivityOptions.newBuilder()
            .setStartToCloseTimeout(Duration.ofMinutes(10))
            .setHeartbeatTimeout(Duration.ofMinutes(2))
            .setRetryOptions(RetryOptions.newBuilder()
                    .setMaximumAttempts(3)
                    .setInitialInterval(Duration.ofSeconds(2))
                    .setMaximumInterval(Duration.ofSeconds(30))
                    .setBackoffCoefficient(2.0)
                    .build())
            .build();

    private final MigrationActivities activities = Workflow.newActivityStub(
            MigrationActivities.class, DEFAULT_OPTIONS);

    private String currentStage = "PENDING";

    @Override
    public MigrationResult migrate(MigrationRequest request) {
        List<Map<String, Object>> stages = new ArrayList<>();
        Map<String, Object> ctx = new LinkedHashMap<>();
        ctx.put("taskId", request.taskId());
        ctx.put("projectId", request.projectId());
        ctx.put("sourceDialect", request.sourceDialect());
        ctx.put("targetDialect", request.targetDialect());
        if (request.options() != null) ctx.put("options", request.options());

        currentStage = "SCHEMA";
        Map<String, Object> schemaOut = activities.runSchemaAnalyzer(ctx);
        stages.add(stageSummary("SCHEMA", schemaOut));
        ctx.put("schema", schemaOut);

        currentStage = "RETRIEVE";
        Map<String, Object> retrieveOut = activities.runContextRetriever(ctx);
        stages.add(stageSummary("RETRIEVE", retrieveOut));
        ctx.put("retrieve", retrieveOut);

        currentStage = "REASON";
        Map<String, Object> reasonOut = activities.runSqlReasoner(ctx);
        stages.add(stageSummary("REASON", reasonOut));
        ctx.put("reason", reasonOut);

        currentStage = "PATCH";
        Map<String, Object> patchOut = activities.runSqlPatcher(ctx);
        stages.add(stageSummary("PATCH", patchOut));
        ctx.put("patch", patchOut);

        currentStage = "CRITIC";
        Map<String, Object> criticOut = activities.runSqlCritic(ctx);
        stages.add(stageSummary("CRITIC", criticOut));
        ctx.put("critic", criticOut);

        currentStage = "REPORT";
        Map<String, Object> reportOut = activities.runReportSummarizer(ctx);
        stages.add(stageSummary("REPORT", reportOut));

        currentStage = "DONE";
        return new MigrationResult(
                request.taskId(),
                allOk(stages) ? "success" : "partial",
                stages,
                reportOut);
    }

    @Override
    public String currentStage() {
        return currentStage;
    }

    private Map<String, Object> stageSummary(String stage, Map<String, Object> out) {
        Map<String, Object> s = new LinkedHashMap<>();
        s.put("stage", stage);
        s.put("ok", out != null && Boolean.TRUE.equals(out.get("_ok")));
        s.put("elapsedMs", out != null ? out.getOrDefault("_elapsedMs", 0) : 0);
        s.put("model", out != null ? out.getOrDefault("_model", "") : "");
        s.put("confidence", out != null ? out.getOrDefault("_confidence", 0.0) : 0.0);
        return s;
    }

    private boolean allOk(List<Map<String, Object>> stages) {
        return stages.stream().allMatch(s -> Boolean.TRUE.equals(s.get("ok")));
    }
}
