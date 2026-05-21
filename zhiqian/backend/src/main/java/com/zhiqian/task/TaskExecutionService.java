package com.zhiqian.task;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.zhiqian.agent.*;
import com.zhiqian.agent.tools.*;
import com.zhiqian.llm.LlmClient;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * v2-step-03 新增：真 LLM 驱动的迁移流水线服务，替代原 {@link TaskSseDemoEmitter} 的硬编码演示数据。
 * <p>
 * 执行思路：
 * <ol>
 *   <li>HTTP 请求进来创建 SseEmitter 后立即返回，避免阻塞 Tomcat 线程</li>
 *   <li>独立 ExecutorService 上构造 AgentGraph + AgentContext，启动 AgentRunner</li>
 *   <li>onStep 回调将每个 Stage 结果转为 SSE "step"、"progress" 事件推给前端</li>
 * </ol>
 */
@Slf4j
@Service
public class TaskExecutionService {

    private final LlmClient llm;
    private final AgentRunner runner;
    private final ObjectMapper mapper = new ObjectMapper();
    private final ExecutorService executor = Executors.newCachedThreadPool();
    private final ConcurrentHashMap<Long, SseEmitter> active = new ConcurrentHashMap<>();

    public TaskExecutionService(LlmClient llm, AgentRunner runner) {
        this.llm = llm;
        this.runner = runner;
        log.info("[TaskExecution] 初始化完成。LLM provider={}, real={}", llm.providerName(), llm.isReal());
    }

    public SseEmitter subscribe(Long taskId) {
        SseEmitter emitter = new SseEmitter(0L);
        active.put(taskId, emitter);
        emitter.onCompletion(() -> active.remove(taskId));
        emitter.onTimeout(() -> active.remove(taskId));
        emitter.onError(t -> active.remove(taskId));
        executor.submit(() -> runPipeline(taskId, emitter));
        return emitter;
    }

    private AgentGraph buildGraph() {
        AgentGraph g = new AgentGraph();
        g.addNode("01-analyzer",  new SchemaAnalyzerAgent(llm));
        g.addNode("02-retriever", new ContextRetrieverAgent(llm));
        g.addNode("03-reasoner",  new SqlReasonerAgent(llm));
        g.addNode("04-patcher",   new SqlPatcherAgent(llm));
        g.addNode("05-critic",    new SqlCriticAgent(llm));
        g.addNode("06-reporter",  new ReportSummarizerAgent(llm));
        g.addEdge("01-analyzer",  ctx -> "02-retriever");
        g.addEdge("02-retriever", ctx -> "03-reasoner");
        g.addEdge("03-reasoner",  ctx -> "04-patcher");
        g.addEdge("04-patcher",   ctx -> "05-critic");
        g.addEdge("05-critic",    ctx -> "06-reporter");
        g.addEdge("06-reporter",  ctx -> null);
        g.entry("01-analyzer");
        return g;
    }

    private void runPipeline(Long taskId, SseEmitter emitter) {
        AgentGraph graph = buildGraph();
        AgentContext ctx = new AgentContext(taskId, 1L);
        int total = 6;
        int[] idx = {0};
        try {
            runner.run(graph, ctx, step -> {
                idx[0]++;
                try {
                    Map<String, Object> evt = new LinkedHashMap<>();
                    evt.put("taskId", taskId);
                    evt.put("stage", step.stage());
                    evt.put("agentName", step.agentName());
                    evt.put("status", step.status());
                    evt.put("elapsedMs", step.elapsedMs());
                    evt.put("model", step.model());
                    evt.put("confidence", step.confidence());
                    evt.put("tokenIn", step.tokenIn());
                    evt.put("tokenOut", step.tokenOut());
                    evt.put("payload", stripUnderscored(step.output()));
                    emitter.send(SseEmitter.event().name("step").data(mapper.writeValueAsString(evt), MediaType.APPLICATION_JSON));
                    int pct = (int) Math.round((idx[0] / (double) total) * 100);
                    emitter.send(SseEmitter.event().name("progress").data(String.valueOf(pct)));
                } catch (Exception e) {
                    log.warn("[Task {}] SSE send failed: {}", taskId, e.getMessage());
                }
            });
            emitter.complete();
        } catch (Exception e) {
            log.error("[Task {}] pipeline failed", taskId, e);
            emitter.completeWithError(e);
        }
    }

    private Map<String, Object> stripUnderscored(Map<String, Object> output) {
        if (output == null) return Map.of();
        Map<String, Object> clean = new LinkedHashMap<>();
        for (var e : output.entrySet()) {
            if (!e.getKey().startsWith("_")) clean.put(e.getKey(), e.getValue());
        }
        return clean;
    }
}
