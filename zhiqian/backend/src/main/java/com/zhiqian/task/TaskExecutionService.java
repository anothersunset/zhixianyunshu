package com.zhiqian.task;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.zhiqian.agent.AgentStep;
import com.zhiqian.project.Project;
import com.zhiqian.report.MigrationReport;
import com.zhiqian.report.MigrationReportRepository;
import jakarta.annotation.PreDestroy;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;

@Slf4j
@Service
public class TaskExecutionService {
    private static final long SSE_TIMEOUT_MS = 30 * 60 * 1000L;

    private final MigrationPipelineService pipeline;
    private final TaskRepository taskRepository;
    private final TaskAgentStepRepository stepRepository;
    private final MigrationReportRepository reportRepository;
    private final ObjectMapper mapper;
    private final ThreadPoolExecutor executor;
    private final ScheduledExecutorService scheduler = Executors.newSingleThreadScheduledExecutor();
    private final ConcurrentHashMap<Long, RunChannel> runs = new ConcurrentHashMap<>();

    public TaskExecutionService(
        MigrationPipelineService pipeline,
        TaskRepository taskRepository,
        TaskAgentStepRepository stepRepository,
        MigrationReportRepository reportRepository,
        ObjectMapper mapper
    ) {
        this.pipeline = pipeline;
        this.taskRepository = taskRepository;
        this.stepRepository = stepRepository;
        this.reportRepository = reportRepository;
        this.mapper = mapper;
        this.executor = new ThreadPoolExecutor(
            4,
            8,
            60,
            TimeUnit.SECONDS,
            new ArrayBlockingQueue<>(100),
            new ThreadPoolExecutor.AbortPolicy()
        );
        scheduler.scheduleAtFixedRate(this::heartbeat, 15, 15, TimeUnit.SECONDS);
    }

    public StartResponse start(Task task, Project project) {
        if ("RUNNING".equals(task.getStatus()) || runs.containsKey(task.getId())) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "task is already running");
        }
        if (task.getSourceSql() == null || task.getSourceSql().isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "task source SQL is empty");
        }

        String runId = "run-" + UUID.randomUUID();
        RunChannel channel = new RunChannel(runId);
        if (runs.putIfAbsent(task.getId(), channel) != null) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "task is already running");
        }

        task.setRunId(runId);
        task.setStatus("RUNNING");
        task.setErrorMessage(null);
        task.setFinishedAt(null);
        taskRepository.save(task);
        try {
            executor.execute(() -> runPipeline(task.getId(), project, channel));
        } catch (java.util.concurrent.RejectedExecutionException exception) {
            runs.remove(task.getId(), channel);
            task.setStatus("PENDING");
            task.setRunId(null);
            taskRepository.save(task);
            throw new ResponseStatusException(HttpStatus.TOO_MANY_REQUESTS, "migration queue is full");
        }
        return new StartResponse(task.getId(), runId, "RUNNING");
    }

    public SseEmitter subscribe(Task task, String runId) {
        if (runId == null || !runId.equals(task.getRunId())) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "run not found for task");
        }
        RunChannel channel = runs.get(task.getId());
        SseEmitter emitter = new SseEmitter(SSE_TIMEOUT_MS);
        if (channel == null) {
            send(emitter, terminalName(task.getStatus()), json(Map.of(
                "taskId", task.getId(),
                "runId", runId,
                "status", task.getStatus()
            )));
            emitter.complete();
            return emitter;
        }

        channel.emitters.add(emitter);
        emitter.onCompletion(() -> channel.emitters.remove(emitter));
        emitter.onTimeout(() -> channel.emitters.remove(emitter));
        emitter.onError(error -> channel.emitters.remove(emitter));
        synchronized (channel.history) {
            for (SseMessage message : channel.history) {
                send(emitter, message.name(), message.data());
            }
        }
        if (channel.completed) {
            emitter.complete();
        }
        return emitter;
    }

    private void runPipeline(Long taskId, Project project, RunChannel channel) {
        Task task = taskRepository.findById(taskId).orElseThrow();
        List<Double> confidences = new ArrayList<>();
        try {
            var result = pipeline.execute(
                new MigrationPipelineService.MigrationInput(
                    taskId,
                    project.getId(),
                    task.getSourceSql(),
                    normalizeDialect(project.getSourceDb()),
                    normalizeDialect(project.getTargetDb()),
                    "full"
                ),
                step -> {
                    persistStep(taskId, step);
                    if (step.confidence() != null) confidences.add(step.confidence());
                    publish(channel, "step", stepEvent(taskId, channel.runId, step));
                    int progress = Math.min(95, channel.stepCount.incrementAndGet() * 100 / 6);
                    publish(channel, "progress", String.valueOf(progress));
                }
            );

            task = taskRepository.findById(taskId).orElseThrow();
            task.setStatus(result.status());
            task.setResultSql(result.resultSql());
            task.setErrorMessage(result.failedStage());
            task.setReviewRequired(result.reviewRequired() ? 1 : 0);
            task.setTotalUnits(result.steps().size());
            task.setAvgConfidence(confidences.stream().mapToDouble(Double::doubleValue).average().orElse(0.0));
            task.setFinishedAt(Instant.now());
            taskRepository.save(task);
            saveReport(task, result.reportMd());

            publish(channel, "progress", "100");
            publish(channel, terminalName(result.status()), json(Map.of(
                "taskId", taskId,
                "runId", channel.runId,
                "status", result.status(),
                "traceId", result.traceId() == null ? "" : result.traceId()
            )));
        } catch (Exception exception) {
            log.error("[Task {}] migration pipeline failed", taskId, exception);
            task = taskRepository.findById(taskId).orElse(task);
            task.setStatus("FAILED");
            task.setErrorMessage(exception.getMessage());
            task.setFinishedAt(Instant.now());
            taskRepository.save(task);
            publish(channel, "failed", json(Map.of(
                "taskId", taskId,
                "runId", channel.runId,
                "status", "FAILED",
                "error", String.valueOf(exception.getMessage())
            )));
        } finally {
            channel.completed = true;
            channel.emitters.forEach(SseEmitter::complete);
            scheduler.schedule(() -> runs.remove(taskId, channel), 5, TimeUnit.MINUTES);
        }
    }

    private void persistStep(Long taskId, AgentStep step) {
        TaskAgentStep entity = new TaskAgentStep();
        entity.setTaskId(taskId);
        entity.setStage(step.stage());
        entity.setAgentName(step.agentName());
        entity.setStatus(step.status());
        entity.setElapsedMs(Math.toIntExact(Math.min(Integer.MAX_VALUE, step.elapsedMs())));
        entity.setConfidence(step.confidence());
        entity.setPayload(json(stripInternal(step.output())));
        entity.setCreatedAt(Instant.now());
        stepRepository.save(entity);
    }

    private void saveReport(Task task, String markdown) {
        MigrationReport report = new MigrationReport();
        report.setTaskId(task.getId());
        report.setTitle(task.getName() + " migration report");
        report.setSummary("status=" + task.getStatus() + ", confidence=" + task.getAvgConfidence());
        report.setArtifactUrl("/api/tasks/" + task.getId() + "/report/download");
        report.setContentMd(markdown);
        report.setCreatedAt(Instant.now());
        reportRepository.save(report);
    }

    private String stepEvent(Long taskId, String runId, AgentStep step) {
        Map<String, Object> event = new LinkedHashMap<>();
        event.put("taskId", taskId);
        event.put("runId", runId);
        event.put("stage", step.stage());
        event.put("agentName", step.agentName());
        event.put("status", step.status());
        event.put("elapsedMs", step.elapsedMs());
        event.put("model", step.model());
        event.put("confidence", step.confidence());
        event.put("tokenIn", step.tokenIn());
        event.put("tokenOut", step.tokenOut());
        event.put("payload", stripInternal(step.output()));
        return json(event);
    }

    private Map<String, Object> stripInternal(Map<String, Object> output) {
        Map<String, Object> clean = new LinkedHashMap<>();
        if (output != null) {
            output.forEach((key, value) -> {
                if (!key.startsWith("_")) clean.put(key, value);
            });
        }
        return clean;
    }

    private void publish(RunChannel channel, String name, String data) {
        SseMessage message = new SseMessage(name, data);
        synchronized (channel.history) {
            channel.history.add(message);
        }
        channel.emitters.removeIf(emitter -> !send(emitter, name, data));
    }

    private boolean send(SseEmitter emitter, String name, String data) {
        try {
            emitter.send(SseEmitter.event().name(name).data(data, MediaType.APPLICATION_JSON));
            return true;
        } catch (Exception exception) {
            return false;
        }
    }

    private void heartbeat() {
        runs.values().stream()
            .filter(channel -> !channel.completed)
            .forEach(channel -> channel.emitters.removeIf(emitter -> !send(emitter, "heartbeat", "{}")));
    }

    private String json(Object value) {
        try {
            return mapper.writeValueAsString(value);
        } catch (JsonProcessingException exception) {
            return "{\"error\":\"serialization failed\"}";
        }
    }

    private String normalizeDialect(String value) {
        String normalized = value == null ? "" : value.toLowerCase();
        if (normalized.contains("mysql")) return "mysql";
        if (normalized.contains("oracle")) return "oracle";
        if (normalized.contains("sqlserver") || normalized.contains("sql server")) return "sqlserver";
        if (normalized.contains("opengauss")) return "opengauss";
        if (normalized.contains("postgres")) return "postgresql";
        return normalized.replaceAll("\\s+.*$", "");
    }

    private String terminalName(String status) {
        return "FAILED".equals(status) ? "failed" : "completed";
    }

    @PreDestroy
    public void shutdown() {
        executor.shutdownNow();
        scheduler.shutdownNow();
    }

    public record StartResponse(Long taskId, String runId, String status) {}
    private record SseMessage(String name, String data) {}

    private static final class RunChannel {
        private final String runId;
        private final List<SseEmitter> emitters = new CopyOnWriteArrayList<>();
        private final List<SseMessage> history = new ArrayList<>();
        private final java.util.concurrent.atomic.AtomicInteger stepCount = new java.util.concurrent.atomic.AtomicInteger();
        private volatile boolean completed;

        private RunChannel(String runId) {
            this.runId = runId;
        }
    }
}
