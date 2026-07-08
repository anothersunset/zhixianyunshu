package com.zhiqian.task;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.zhiqian.agent.*;
import com.zhiqian.agent.tools.*;
import com.zhiqian.llm.LlmClient;
import com.zhiqian.observability.LangfuseClient;
import com.zhiqian.observability.TraceHandle;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * v2-step-03 新增: 真 LLM 驱动的迁移流水线服务。
 * v2-step-08 新增: 每个 taskId 起一个 'task.migration' 根 trace,贯穿所有 stage + LLM 调用;
 *                  SSE step 事件额外携 traceId,前端可点按钮跳转 Langfuse UI 定位本次任务。
 */
@Slf4j
@Service
public class TaskExecutionService {

    private final LlmClient llm;
    private final AgentRunner runner;
    private final LangfuseClient langfuse;
    private final ObjectMapper mapper = new ObjectMapper();
    private final ExecutorService executor = Executors.newCachedThreadPool();
    private final ConcurrentHashMap<Long, SseEmitter> active = new ConcurrentHashMap<>();

    public TaskExecutionService(LlmClient llm, AgentRunner runner, LangfuseClient langfuse) {
        this.llm = llm;
        this.runner = runner;
        this.langfuse = langfuse;
        log.info("[TaskExecution] 初始化完成。LLM provider={}, real={}, langfuse={}",
                llm.providerName(), llm.isReal(),
                langfuse.isEnabled() ? "enabled@" + langfuse.getHost() : "disabled");
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

    /** 反思回环上限：critic 判 NEEDS_FIX 时最多送回 patcher 重修的轮数，防止两个 LLM 节点互相不满意导致死循环。 */
    private static final int MAX_REFINE_ROUNDS = 1;

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
        // 反思回环：SqlCriticAgent 输出 needs_correction，SqlPatcherAgent 会把 state 里的
        // critique 拼进重修提示词——两端早已就位，这条条件边把回环真正接通。
        g.addEdge("05-critic",    ctx -> {
            boolean needsFix = Boolean.TRUE.equals(ctx.state().get("needs_correction"));
            int round = ctx.state().get("refine_round") instanceof Number n ? n.intValue() : 0;
            if (needsFix && round < MAX_REFINE_ROUNDS) {
                ctx.state().put("refine_round", round + 1);
                return "04-patcher";
            }
            return "06-reporter";
        });
        g.addEdge("06-reporter",  ctx -> null);
        g.entry("01-analyzer");
        return g;
    }

    private void runPipeline(Long taskId, SseEmitter emitter) {
        AgentGraph graph = buildGraph();
        AgentContext ctx = new AgentContext(taskId, 1L);
        int total = 6; // 标称 6 站；反思回环最多再多跑 2 站，进度百分比封顶 100
        int[] idx = {0};

        // v2-step-08: 为本次 task 起一个 root trace
        TraceHandle trace = langfuse.newTrace(
                "task.migration",
                Map.of("taskId", taskId),
                Map.of(
                        "llm_provider", llm.providerName(),
                        "llm_real", llm.isReal(),
                        "agents", 6
                ),
                List.of("backend", "migration", "task-" + taskId)
        );

        boolean[] failed = {false};
        String[] failedStage = {null};
        try {
            runner.run(graph, ctx, step -> {
                idx[0]++;
                if ("FAIL".equals(step.status())) {
                    failed[0] = true;
                    failedStage[0] = step.stage();
                }
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
                    if (!trace.isNoop()) evt.put("traceId", trace.getTraceId());
                    emitter.send(SseEmitter.event().name("step").data(mapper.writeValueAsString(evt), MediaType.APPLICATION_JSON));
                    int pct = Math.min(100, (int) Math.round((idx[0] / (double) total) * 100));
                    emitter.send(SseEmitter.event().name("progress").data(String.valueOf(pct)));
                } catch (Exception e) {
                    log.warn("[Task {}] SSE send failed: {}", taskId, e.getMessage());
                }
            }, trace);
            if (failed[0]) {
                // 某一站 FAIL 后 runner 已停止执行，但流程并未成功——不能再上报 completed。
                log.warn("[Task {}] pipeline halted at stage '{}'", taskId, failedStage[0]);
                trace.finish(
                        Map.of("status", "failed", "failed_stage", String.valueOf(failedStage[0]),
                                "stages_executed", idx[0]),
                        Map.of("task_done", false)
                );
                try {
                    emitter.send(SseEmitter.event().name("failed").data(
                            mapper.writeValueAsString(Map.of("stage", failedStage[0], "stagesExecuted", idx[0]))));
                } catch (Exception ignore) {
                    // SSE 已断开则忽略，trace 已记录失败
                }
            } else {
                trace.finish(
                        Map.of("status", "completed", "stages_executed", idx[0]),
                        Map.of("task_done", true)
                );
            }
            emitter.complete();
        } catch (Exception e) {
            log.error("[Task {}] pipeline failed", taskId, e);
            trace.finish(
                    Map.of("status", "failed", "error", String.valueOf(e.getMessage()), "stages_executed", idx[0]),
                    Map.of("task_done", false)
            );
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
