package com.zhiqian.a2a;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.core.task.TaskExecutor;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;

@Component
public class A2ATaskExecutor {
    private final RestTemplate rest;
    private final TaskExecutor taskExecutor;
    private final String ragUrl;

    @Autowired
    public A2ATaskExecutor(
        @Qualifier("migrateExecutor") TaskExecutor taskExecutor,
        RestTemplateBuilder restTemplateBuilder,
        @Value("${app.rag.base-url:http://localhost:8001}") String ragUrl
    ) {
        this(taskExecutor, restTemplateBuilder
                // RAG 服务无响应时不能无限占用执行线程
                .setConnectTimeout(Duration.ofSeconds(5))
                .setReadTimeout(Duration.ofSeconds(60))
                .build(),
            ragUrl);
    }

    A2ATaskExecutor(TaskExecutor taskExecutor, RestTemplate rest, String ragUrl) {
        this.taskExecutor = taskExecutor;
        this.rest = rest;
        this.ragUrl = ragUrl.replaceFirst("/+$", "");
    }

    public CompletableFuture<Void> execute(A2ATask task) {
        return CompletableFuture.runAsync(() -> {
            try {
                task.state = "working";
                task.updatedAt = Instant.now();
                run(task);
            } catch (Exception exception) {
                task.state = "failed";
                task.errorMessage = exception.getMessage();
                task.updatedAt = Instant.now();
            }
        }, taskExecutor);
    }

    @SuppressWarnings("unchecked")
    public void run(A2ATask task) {
        task.state = "working";
        task.updatedAt = Instant.now();
        try {
            Map<String, Object> input = task.input == null ? Map.of() : task.input;
            String skill = String.valueOf(input.getOrDefault("skill", "sql.transpile"));
            Object rawArguments = input.get("arguments");
            if (rawArguments != null && !(rawArguments instanceof Map<?, ?>)) {
                throw new IllegalArgumentException("message.arguments must be an object");
            }
            Map<String, Object> args = rawArguments == null
                ? Map.of() : (Map<String, Object>) rawArguments;
            String text = String.valueOf(input.getOrDefault("text", ""));

            Object result = switch (skill) {
                case "sql.transpile" -> callRag("/transpile", buildTranspileBody(args, text));
                case "sql.explain" -> explain(args, text);
                case "schema.analyze" -> callRag("/structured/schema-analysis", buildSchemaBody(args, text));
                case "migration.plan" -> callRag("/crag/query", Map.of(
                    "question", text.isBlank() ? args.getOrDefault("question", "migration plan") : text,
                    "top_k", args.getOrDefault("top_k", 5),
                    "use_web", args.getOrDefault("use_web", true)
                ));
                default -> throw new IllegalArgumentException("unknown skill: " + skill);
            };

            task.artifacts.add(Map.of(
                "name", skill + "-result",
                "parts", List.of(Map.of("type", "data", "data", result))
            ));
            task.history.add(Map.of(
                "role", "agent",
                "timestamp", Instant.now().toString(),
                "summary", "Executed skill: " + skill
            ));
            task.state = "completed";
            task.updatedAt = Instant.now();
        } catch (RuntimeException exception) {
            task.state = "failed";
            task.errorMessage = exception.getMessage();
            task.updatedAt = Instant.now();
            throw exception;
        }
    }

    private Map<String, Object> buildTranspileBody(Map<String, Object> args, String text) {
        return Map.of(
            "sql", args.getOrDefault("source_sql", text),
            "source", args.getOrDefault("source_dialect", "mysql"),
            "target", args.getOrDefault("target_dialect", "opengauss")
        );
    }

    private Map<String, Object> buildSchemaBody(Map<String, Object> args, String text) {
        return Map.of(
            "schema_summary", args.getOrDefault("schema_summary", args.getOrDefault("ddl", text)),
            "tables_total", args.getOrDefault("tables_total", 0)
        );
    }

    @SuppressWarnings("unchecked")
    private Object explain(Map<String, Object> args, String text) {
        Map<String, Object> transpiled = (Map<String, Object>) callRag(
            "/transpile",
            buildTranspileBody(args, text)
        );
        String targetSql = String.valueOf(args.getOrDefault(
            "target_sql",
            transpiled.getOrDefault("target", "")
        ));
        return callRag("/structured/transpile-explain", Map.of(
            "source_sql", args.getOrDefault("source_sql", text),
            "target_sql", targetSql,
            "source_dialect", args.getOrDefault("source_dialect", "mysql"),
            "target_dialect", args.getOrDefault("target_dialect", "opengauss")
        ));
    }

    private Object callRag(String path, Map<String, Object> body) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        Object response = rest.postForObject(ragUrl + path, new HttpEntity<>(body, headers), Map.class);
        if (response == null) {
            throw new IllegalStateException("RAG returned an empty response for " + path);
        }
        return response;
    }
}
