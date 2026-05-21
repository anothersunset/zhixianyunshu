package com.zhiqian.agent;

import com.zhiqian.observability.LangfuseClient;
import com.zhiqian.observability.TraceHandle;
import org.springframework.stereotype.Component;

import java.time.Instant;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.function.Consumer;

/**
 * 顺序执行 AgentGraph。
 *
 * <p>v2-step-03 增强: 从 tool 输出中提取 _model / _confidence / _tokenIn / _tokenOut 填到 AgentStep。</p>
 *
 * <p>v2-step-08 增强: 接受可选 {@link TraceHandle},为每个 stage 发一段 span,并把 trace 上下文 bind 到
 * ThreadLocal 供 {@link com.zhiqian.llm.DeepSeekLlmClient} 自动 attach generation,在 Langfuse 看到完整树:
 * <pre>
 * task.migration (root)
 * ├── 01-analyzer:schema_analyzer (span)
 * │   └── llm.chat (generation, model=deepseek-chat, tokens 、 prompt 、 completion)
 * ├── 02-retriever:context_retriever (span)
 * │   └── llm.chat (generation)
 * └── …
 * </pre>
 * 向后兼容: 保留原 3 参 run() 重载。</p>
 */
@Component
public class AgentRunner {

    /** 原 3 参重载 - 向后兼容。 */
    public void run(AgentGraph graph, AgentContext ctx, Consumer<AgentStep> onStep) {
        run(graph, ctx, onStep, null);
    }

    /** v2-step-08 新增 4 参重载 - 接受 parentTrace。 */
    public void run(AgentGraph graph, AgentContext ctx, Consumer<AgentStep> onStep, TraceHandle parentTrace) {
        String cur = graph.entryNode();
        while (cur != null) {
            long t0 = System.currentTimeMillis();
            Instant startInstant = Instant.now();
            var tool = graph.node(cur);
            Map<String, Object> input = new HashMap<>(ctx.state());
            Map<String, Object> output;
            String status = "OK";

            boolean bound = false;
            if (parentTrace != null && !parentTrace.isNoop()) {
                LangfuseClient.bind(parentTrace);
                bound = true;
            }
            try {
                output = tool.run(ctx, input);
                ctx.state().putAll(output);
            } catch (Exception e) {
                output = new HashMap<>();
                output.put("error", e.getMessage());
                status = "FAIL";
            } finally {
                if (bound) LangfuseClient.unbind();
            }
            Instant endInstant = Instant.now();
            long elapsed = System.currentTimeMillis() - t0;
            String model = output.get("_model") instanceof String s ? s : null;
            Double conf = output.get("_confidence") instanceof Number n ? n.doubleValue() : null;
            Integer tokenIn = output.get("_tokenIn") instanceof Number n ? n.intValue() : null;
            Integer tokenOut = output.get("_tokenOut") instanceof Number n ? n.intValue() : null;

            // 上报 stage 作为 trace 的 span (不走上下文推断,点到点上报,避免 Langfuse SDK 嵌套语义复杂)
            if (parentTrace != null && !parentTrace.isNoop()) {
                Map<String, Object> meta = new LinkedHashMap<>();
                if (model != null) meta.put("model", model);
                if (conf != null) meta.put("confidence", conf);
                if (tokenIn != null) meta.put("tokenIn", tokenIn);
                if (tokenOut != null) meta.put("tokenOut", tokenOut);
                meta.put("status", status);
                meta.put("elapsed_ms", elapsed);
                Map<String, Object> outClean = new LinkedHashMap<>();
                for (var e : output.entrySet()) {
                    if (!e.getKey().startsWith("_")) outClean.put(e.getKey(), e.getValue());
                }
                parentTrace.span(cur + ":" + tool.name(), startInstant, endInstant, input, outClean, meta);
            }

            onStep.accept(new AgentStep(cur, tool.name(), input, output, model, conf, elapsed, tokenIn, tokenOut, status));
            if ("FAIL".equals(status)) break;
            cur = graph.next(cur, ctx);
        }
    }
}
