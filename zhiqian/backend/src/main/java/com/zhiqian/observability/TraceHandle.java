package com.zhiqian.observability;

import java.time.Instant;
import java.util.List;
import java.util.Map;

/**
 * v2-step-08: Langfuse trace 句柄。
 *
 * <p>disabled 路径走 {@link #NOOP} 单例,所有方法立即 return 零开销。调用代码不需为两种开关写两套分支。
 */
public class TraceHandle {

    /** 全局 noop 单例。LangfuseClient disabled 时 newTrace() 返回这个。 */
    public static final TraceHandle NOOP = new TraceHandle(null, null, "noop");

    private final LangfuseClient client;
    private final String traceId;
    private final String name;

    TraceHandle(LangfuseClient client, String traceId, String name) {
        this.client = client;
        this.traceId = traceId;
        this.name = name;
    }

    public String getTraceId() { return traceId; }
    public String getName() { return name; }
    public boolean isNoop() { return client == null; }

    public void span(String spanName, Instant start, Instant end,
                     Map<String, Object> input, Map<String, Object> output) {
        span(spanName, start, end, input, output, null);
    }

    public void span(String spanName, Instant start, Instant end,
                     Map<String, Object> input, Map<String, Object> output, Map<String, Object> metadata) {
        if (isNoop()) return;
        client.emitSpan(traceId, spanName, start, end, input, output, metadata);
    }

    public void generation(String genName, String model, Instant start, Instant end,
                            List<Map<String, String>> messages, String completion,
                            Integer promptTokens, Integer completionTokens) {
        if (isNoop()) return;
        client.emitGeneration(traceId, genName, model, start, end, messages, completion,
                promptTokens, completionTokens);
    }

    public void finish(Map<String, Object> output, Map<String, Object> metadata) {
        if (isNoop()) return;
        client.closeTrace(traceId, output, metadata);
    }
}
