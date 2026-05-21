package com.zhiqian.a2a;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;

import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import com.zhiqian.common.Result;

/**
 * v2-step-24: A2A task endpoint。
 *
 * POST /a2a/tasks/send           同步 (小任务)
 * POST /a2a/tasks/sendSubscribe  SSE 流 (长任务, working → completed/failed)
 * GET  /a2a/tasks/{id}           查状态
 */
@RestController
@RequestMapping("/a2a/tasks")
public class A2ATaskController {

    private final A2ATaskStore store;
    private final A2ATaskExecutor executor;

    public A2ATaskController(A2ATaskStore store, A2ATaskExecutor executor) {
        this.store = store;
        this.executor = executor;
    }

    @PostMapping("/send")
    public ResponseEntity<Map<String, Object>> send(@RequestBody Map<String, Object> body) {
        A2ATask task = buildTask(body);
        store.save(task);
        executor.execute(task);
        return ResponseEntity.ok(task.toJson());
    }

    @PostMapping(value = "/sendSubscribe", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter sendSubscribe(@RequestBody Map<String, Object> body) {
        A2ATask task = buildTask(body);
        store.save(task);
        SseEmitter emitter = new SseEmitter(TimeUnit.MINUTES.toMillis(5));

        // 1) 马上推 submitted
        emit(emitter, "task", task.toJson());

        CompletableFuture.runAsync(() -> {
            try {
                task.state = "working";
                task.updatedAt = Instant.now();
                emit(emitter, "status", task.toJson());

                executor.run(task);

                emit(emitter, "artifact", Map.of(
                    "taskId", task.id, "artifacts", task.artifacts
                ));
                emit(emitter, "status", task.toJson());
                emitter.complete();
            } catch (Exception e) {
                task.state = "failed";
                task.errorMessage = e.getMessage();
                task.updatedAt = Instant.now();
                emit(emitter, "status", task.toJson());
                emitter.completeWithError(e);
            }
        });
        return emitter;
    }

    @GetMapping("/{id}")
    public Result<Map<String, Object>> get(@PathVariable String id) {
        A2ATask t = store.get(id);
        if (t == null) return Result.fail(404, "task not found: " + id);
        return Result.ok(t.toJson());
    }

    @GetMapping
    public Result<List<Map<String, Object>>> list() {
        return Result.ok(store.all().stream().map(A2ATask::toJson).toList());
    }

    @SuppressWarnings("unchecked")
    private A2ATask buildTask(Map<String, Object> body) {
        A2ATask t = new A2ATask();
        t.id = String.valueOf(body.getOrDefault("id", UUID.randomUUID().toString()));
        t.sessionId = (String) body.getOrDefault("sessionId", "");
        t.state = "submitted";
        t.createdAt = Instant.now();
        t.updatedAt = t.createdAt;
        Object msg = body.get("message");
        if (msg instanceof Map) t.input = (Map<String, Object>) msg;
        else t.input = Map.of("text", String.valueOf(body.getOrDefault("text", "")));
        return t;
    }

    private void emit(SseEmitter e, String event, Object data) {
        try { e.send(SseEmitter.event().name(event).data(data)); }
        catch (Exception ex) { /* 客户端断连忽略 */ }
    }
}
