package com.zhiqian.task;

import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

@Slf4j
@Component
@RequiredArgsConstructor
public class TaskSseDemoEmitter {

    private final ObjectMapper mapper = new ObjectMapper();
    private final ScheduledExecutorService scheduler = Executors.newScheduledThreadPool(2);
    private final ConcurrentHashMap<Long, SseEmitter> active = new ConcurrentHashMap<>();

    private static final List<Map<String, Object>> STEPS = List.of(
        Map.of("stage", "01-bootstrap",  "agentName", "Bootstrap", "status", "OK", "elapsedMs", 120,  "payload", Map.of("msg", "已加载项目表结构")),
        Map.of("stage", "02-analyzer",   "agentName", "Analyzer",  "status", "OK", "elapsedMs", 850,  "payload", Map.of("files", 312, "sqls", 78, "configs", 19)),
        Map.of("stage", "03-ckg-build",  "agentName", "CkgBuilder","status", "OK", "elapsedMs", 410,  "payload", Map.of("nodes", 1842, "edges", 5631)),
        Map.of("stage", "04-retriever",  "agentName", "Retriever", "status", "OK", "elapsedMs", 220,  "confidence", 0.78, "payload", Map.of("top_k", 50, "top_n", 5)),
        Map.of("stage", "05-reasoner",   "agentName", "Reasoner",  "status", "OK", "elapsedMs", 1300, "confidence", 0.81, "payload", Map.of("risk_units", 14)),
        Map.of("stage", "06-patcher",    "agentName", "Patcher",   "status", "OK", "elapsedMs", 780,  "confidence", 0.89, "payload", Map.of("patches", 12, "review_required", 2)),
        Map.of("stage", "07-validator",  "agentName", "Validator", "status", "OK", "elapsedMs", 540,  "confidence", 0.92, "payload", Map.of("scripts", 18)),
        Map.of("stage", "08-reporter",   "agentName", "Reporter",  "status", "OK", "elapsedMs", 180,  "payload", Map.of("report_url", "/api/reports/demo.html"))
    );

    public SseEmitter subscribe(Long taskId) {
        SseEmitter emitter = new SseEmitter(0L);
        active.put(taskId, emitter);
        emitter.onCompletion(() -> active.remove(taskId));
        emitter.onTimeout(() -> active.remove(taskId));

        long delay = 0;
        int total = STEPS.size();
        for (int i = 0; i < total; i++) {
            final int idx = i;
            delay += 800;
            scheduler.schedule(() -> {
                try {
                    Map<String, Object> step = new java.util.HashMap<>(STEPS.get(idx));
                    step.put("taskId", taskId);
                    emitter.send(SseEmitter.event()
                        .name("step")
                        .data(mapper.writeValueAsString(step), MediaType.APPLICATION_JSON));
                    int pct = (int) Math.round(((idx + 1) / (double) total) * 100);
                    emitter.send(SseEmitter.event().name("progress").data(String.valueOf(pct)));
                    if (idx == total - 1) emitter.complete();
                } catch (IOException e) {
                    log.warn("sse send failed: {}", e.getMessage());
                    emitter.completeWithError(e);
                }
            }, delay, TimeUnit.MILLISECONDS);
        }
        return emitter;
    }

    private static final org.springframework.http.MediaType MediaType_APPLICATION_JSON = org.springframework.http.MediaType.APPLICATION_JSON;

    // alias to avoid extra import in inner usage above
    private static class MediaType {
        static final org.springframework.http.MediaType APPLICATION_JSON = org.springframework.http.MediaType.APPLICATION_JSON;
    }
}
