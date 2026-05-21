package com.zhiqian.observability;

import jakarta.annotation.PreDestroy;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

/**
 * v2-step-08: Langfuse Java 轻量客户端。
 *
 * <p>零额外依赖(Langfuse Java SDK 不存在,官方推荐 OTel,但 OTel-GenAI 公约集成成本高),
 * 直接调 Public Ingestion API <code>POST /api/public/ingestion {batch:[…]}</code> + HTTP Basic Auth。
 * 与 RAG 端 <code>observability.py</code> 全面对称。
 *
 * <p>设计要点:
 * <ul>
 *   <li><b>完全可选</b>: keys 留空时 enabled=false,所有 emit 方法立即返回,零开销。</li>
 *   <li><b>异步上报</b>: single-thread daemon executor 队列,业务线程零等待。</li>
 *   <li><b>ThreadLocal trace context</b>: AgentRunner bind/unbind,DeepSeekLlmClient 调 current() 自动 attach generation。</li>
 *   <li><b>secret 不入日志</b>: 仅初始化 INFO host,从不打印 keys。</li>
 * </ul>
 */
@Component
public class LangfuseClient {

    private static final Logger log = LoggerFactory.getLogger(LangfuseClient.class);
    private static final ThreadLocal<TraceHandle> CURRENT = new ThreadLocal<>();

    private final LangfuseProperties props;
    private final boolean enabled;
    private final RestClient client;
    private final ExecutorService flushExec;

    public LangfuseClient(LangfuseProperties props) {
        this.props = props;
        boolean canEnable = props.isEnabled()
                && props.getPublicKey() != null && !props.getPublicKey().isBlank()
                && props.getSecretKey() != null && !props.getSecretKey().isBlank();
        if (canEnable) {
            String auth = Base64.getEncoder().encodeToString(
                    (props.getPublicKey() + ":" + props.getSecretKey()).getBytes(StandardCharsets.UTF_8));
            SimpleClientHttpRequestFactory rf = new SimpleClientHttpRequestFactory();
            rf.setConnectTimeout((int) Duration.ofSeconds(5).toMillis());
            rf.setReadTimeout((int) Duration.ofSeconds(10).toMillis());
            this.client = RestClient.builder()
                    .baseUrl(props.getHost())
                    .requestFactory(rf)
                    .defaultHeader(HttpHeaders.AUTHORIZATION, "Basic " + auth)
                    .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                    .build();
            this.flushExec = Executors.newSingleThreadExecutor(r -> {
                Thread t = new Thread(r, "langfuse-flush");
                t.setDaemon(true);
                return t;
            });
            this.enabled = true;
            log.info("[langfuse] enabled host={} (Public Ingestion API)", props.getHost());
        } else {
            this.client = null;
            this.flushExec = null;
            this.enabled = false;
            log.info("[langfuse] disabled (set app.langfuse.public-key/secret-key to enable)");
        }
    }

    public boolean isEnabled() { return enabled; }
    public String getHost() { return enabled ? props.getHost() : ""; }

    /** 创建根 trace。disabled 返回 NOOP 单例。 */
    public TraceHandle newTrace(String name, Map<String, Object> input,
                                 Map<String, Object> metadata, List<String> tags) {
        if (!enabled) return TraceHandle.NOOP;
        String traceId = UUID.randomUUID().toString();
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("id", traceId);
        body.put("timestamp", Instant.now().toString());
        body.put("name", name);
        if (input != null) body.put("input", input);
        if (metadata != null) body.put("metadata", metadata);
        if (tags != null) body.put("tags", tags);
        emit("trace-create", body);
        return new TraceHandle(this, traceId, name);
    }

    void closeTrace(String traceId, Map<String, Object> output, Map<String, Object> metadata) {
        if (!enabled) return;
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("id", traceId);
        if (output != null) body.put("output", output);
        if (metadata != null) body.put("metadata", metadata);
        emit("trace-create", body); // upsert
    }

    void emitSpan(String traceId, String name, Instant start, Instant end,
                  Map<String, Object> input, Map<String, Object> output, Map<String, Object> metadata) {
        if (!enabled) return;
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("id", UUID.randomUUID().toString());
        body.put("traceId", traceId);
        body.put("name", name);
        body.put("startTime", start.toString());
        body.put("endTime", end.toString());
        if (input != null) body.put("input", input);
        if (output != null) body.put("output", output);
        if (metadata != null) body.put("metadata", metadata);
        emit("span-create", body);
    }

    void emitGeneration(String traceId, String name, String model, Instant start, Instant end,
                        List<Map<String, String>> messages, String completion,
                        Integer promptTokens, Integer completionTokens) {
        if (!enabled) return;
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("id", UUID.randomUUID().toString());
        body.put("traceId", traceId);
        body.put("name", name);
        body.put("model", model);
        body.put("startTime", start.toString());
        body.put("endTime", end.toString());
        if (messages != null) body.put("input", messages);
        if (completion != null) body.put("output", completion);
        Map<String, Object> usage = new LinkedHashMap<>();
        if (promptTokens != null) usage.put("input", promptTokens);
        if (completionTokens != null) usage.put("output", completionTokens);
        if (promptTokens != null && completionTokens != null) {
            usage.put("total", promptTokens + completionTokens);
            usage.put("unit", "TOKENS");
        }
        if (!usage.isEmpty()) body.put("usage", usage);
        emit("generation-create", body);
    }

    private void emit(String type, Map<String, Object> body) {
        if (!enabled) return;
        Map<String, Object> event = Map.of(
                "id", UUID.randomUUID().toString(),
                "timestamp", Instant.now().toString(),
                "type", type,
                "body", body
        );
        flushExec.submit(() -> {
            try {
                client.post()
                        .uri("/api/public/ingestion")
                        .body(Map.of("batch", List.of(event)))
                        .retrieve()
                        .toBodilessEntity();
            } catch (Exception e) {
                log.debug("[langfuse] ingestion 失败 type={}: {}", type, e.getMessage());
            }
        });
    }

    @PreDestroy
    public void shutdown() {
        if (flushExec != null) {
            flushExec.shutdown();
            try {
                flushExec.awaitTermination(3, TimeUnit.SECONDS);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
    }

    // ───── ThreadLocal trace context ─────
    public static void bind(TraceHandle handle) { CURRENT.set(handle); }
    public static void unbind() { CURRENT.remove(); }
    public static TraceHandle current() { return CURRENT.get(); }
}
