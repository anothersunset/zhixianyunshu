package com.zhiqian.temporal;

import com.zhiqian.temporal.workflow.MigrationRequest;
import com.zhiqian.temporal.workflow.MigrationWorkflow;
import io.temporal.client.WorkflowClient;
import io.temporal.client.WorkflowOptions;
import io.temporal.client.WorkflowStub;
import jakarta.validation.constraints.NotBlank;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.time.Duration;
import java.util.Map;

/**
 * v2-step-14: Temporal HTTP 入口。
 *
 * <p>不用 @ConditionalOnBean 让 controller 本身始终装载, 在端点里判 client 为空 返 503。
 * 这样 enabled=false 时也能给前端一个明确的 disabled 提示, 而不是 404。
 */
@Slf4j
@RestController
@RequestMapping("/api/temporal")
@RequiredArgsConstructor
public class TemporalMigrationController {

    private final ObjectProvider<WorkflowClient> clientProvider;
    private final TemporalProperties props;

    public record StartReq(
            long taskId,
            long projectId,
            @NotBlank String sourceDialect,
            @NotBlank String targetDialect,
            Map<String, Object> options
    ) {}

    public record StartResp(String wid, String runId, String taskQueue) {}

    public record StatusResp(String wid, String stage, String message) {}

    @PostMapping("/start")
    public ResponseEntity<?> start(@RequestBody StartReq req) {
        WorkflowClient client = clientProvider.getIfAvailable();
        if (client == null) {
            return ResponseEntity.status(503).body(Map.of(
                    "ok", false,
                    "error", "Temporal disabled. Set app.temporal.enabled=true and start temporal-server."));
        }
        String wid = "migration-" + req.taskId() + "-" + System.currentTimeMillis();
        MigrationWorkflow stub = client.newWorkflowStub(
                MigrationWorkflow.class,
                WorkflowOptions.newBuilder()
                        .setTaskQueue(props.getTaskQueue())
                        .setWorkflowId(wid)
                        .setWorkflowExecutionTimeout(Duration.ofMinutes(props.getWorkflowExecutionTimeoutMinutes()))
                        .build());
        WorkflowClient.start(stub::migrate,
                new MigrationRequest(
                        req.taskId(), req.projectId(),
                        req.sourceDialect(), req.targetDialect(),
                        req.options()));
        String runId = WorkflowStub.fromTyped(stub).getExecution().getRunId();
        log.info("[temporal] started workflow wid={} runId={}", wid, runId);
        return ResponseEntity.ok(new StartResp(wid, runId, props.getTaskQueue()));
    }

    @GetMapping("/status/{wid}")
    public ResponseEntity<?> status(@PathVariable String wid) {
        WorkflowClient client = clientProvider.getIfAvailable();
        if (client == null) {
            return ResponseEntity.status(503).body(Map.of(
                    "ok", false,
                    "error", "Temporal disabled."));
        }
        try {
            MigrationWorkflow stub = client.newWorkflowStub(MigrationWorkflow.class, wid);
            String stage = stub.currentStage();
            return ResponseEntity.ok(new StatusResp(wid, stage, "running"));
        } catch (Exception e) {
            log.warn("[temporal] status query failed wid={} {}", wid, e.getMessage());
            return ResponseEntity.status(404).body(Map.of(
                    "ok", false,
                    "error", "workflow not found or completed: " + e.getMessage()));
        }
    }
}
