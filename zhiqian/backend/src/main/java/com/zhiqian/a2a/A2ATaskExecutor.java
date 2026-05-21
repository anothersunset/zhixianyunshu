package com.zhiqian.a2a;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

/**
 * v2-step-24: A2A 任务执行器。从 input 提取 skill + arguments,
 * 调 RAG (transpile / structured / crag) 并把返装为 A2A artifact。
 */
@Component
public class A2ATaskExecutor {

    private final RestTemplate rest = new RestTemplate();
    @Value("${zhiqian.rag.base-url:http://localhost:8001}") private String ragUrl;

    public CompletableFuture<Void> execute(A2ATask task) {
        return CompletableFuture.runAsync(() -> {
            try {
                task.state = "working";
                task.updatedAt = Instant.now();
                run(task);
            } catch (Exception e) {
                task.state = "failed";
                task.errorMessage = e.getMessage();
                task.updatedAt = Instant.now();
            }
        });
    }

    /** 同步版, sendSubscribe 复用。 */
    @SuppressWarnings("unchecked")
    public void run(A2ATask task) {
        Map<String, Object> input = task.input == null ? Map.of() : task.input;
        String skill = String.valueOf(input.getOrDefault("skill", "sql.transpile"));
        Map<String, Object> args = (Map<String, Object>) input.getOrDefault("arguments", Map.of());
        String text = String.valueOf(input.getOrDefault("text", ""));

        Object result = switch (skill) {
            case "sql.transpile"   -> callRag("/transpile", buildTranspileBody(args, text));
            case "sql.explain"     -> callRag("/structured/transpile-explain", buildTranspileBody(args, text));
            case "schema.analyze"  -> callRag("/structured/schema-analysis", buildSchemaBody(args, text));
            case "migration.plan"  -> callRag("/crag/query", Map.of("query",
                    text.isBlank() ? args.getOrDefault("question", "请生成迁移计划") : text));
            default -> Map.of("error", "unknown skill: " + skill);
        };

        task.artifacts.add(Map.of(
            "name", skill + "-result",
            "parts", List.of(Map.of("type", "data", "data", result))
        ));
        task.history.add(Map.of("role", "agent", "timestamp", Instant.now().toString(),
                "summary", "Executed skill: " + skill));
        task.state = "completed";
        task.updatedAt = Instant.now();
    }

    private Map<String, Object> buildTranspileBody(Map<String, Object> args, String text) {
        return Map.of(
            "source_sql", args.getOrDefault("source_sql", text),
            "source_dialect", args.getOrDefault("source_dialect", "mysql"),
            "target_dialect", args.getOrDefault("target_dialect", "opengauss")
        );
    }

    private Map<String, Object> buildSchemaBody(Map<String, Object> args, String text) {
        return Map.of(
            "ddl", args.getOrDefault("ddl", text),
            "dialect", args.getOrDefault("dialect", "mysql")
        );
    }

    private Object callRag(String path, Map<String, Object> body) {
        HttpHeaders h = new HttpHeaders();
        h.setContentType(MediaType.APPLICATION_JSON);
        return rest.postForObject(ragUrl + path, new HttpEntity<>(body, h), Map.class);
    }
}
