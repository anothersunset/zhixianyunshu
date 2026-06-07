package com.zhiqian.migration;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.zhiqian.agent.AgentContext;
import com.zhiqian.agent.AgentGraph;
import com.zhiqian.agent.AgentRunner;
import com.zhiqian.agent.AgentStep;
import com.zhiqian.agent.tools.ContextRetrieverAgent;
import com.zhiqian.agent.tools.ReportSummarizerAgent;
import com.zhiqian.agent.tools.SchemaAnalyzerAgent;
import com.zhiqian.agent.tools.SqlCriticAgent;
import com.zhiqian.agent.tools.SqlPatcherAgent;
import com.zhiqian.agent.tools.SqlReasonerAgent;
import com.zhiqian.llm.LlmClient;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicLong;

@RestController
public class MigrationEvalController {

    private static final List<String> RETRIEVAL_CHOICES = List.of("bm25", "vector", "vector_rerank", "crag", "full");
    private static final AtomicLong TASK_ID = new AtomicLong(90_000L);

    private final LlmClient llm;
    private final AgentRunner runner;
    private final ObjectMapper mapper;

    public MigrationEvalController(LlmClient llm, AgentRunner runner, ObjectMapper mapper) {
        this.llm = llm;
        this.runner = runner;
        this.mapper = mapper;
    }

    @PostMapping({"/migrate", "/api/migrate"})
    public ResponseEntity<MigrateResponse> migrate(@RequestBody MigrateRequest req) {
        String retrieval = normalizeRetrieval(req.retrieval());
        String pair = req.pair() == null || req.pair().isBlank() ? "mysql->opengauss" : req.pair();
        String sourceSql = req.source_sql() == null ? "" : req.source_sql();

        AgentContext ctx = new AgentContext(TASK_ID.incrementAndGet(), 1L);
        ctx.state().put("source_sql", sourceSql);
        ctx.state().put("pair", pair);
        ctx.state().put("retrieval", retrieval);
        ctx.state().put("sourceDialect", sourceDialect(pair));
        ctx.state().put("targetDialect", targetDialect(pair));

        List<Map<String, Object>> stages = new ArrayList<>();
        runner.run(buildGraph(), ctx, step -> stages.add(stageSnapshot(step)));
        List<String> retrievedIds = extractRetrievedIds(ctx.state().get("retrieved"));

        if (!llm.isReal()) {
            return ResponseEntity.ok(new MigrateResponse(
                "",
                List.of("LLM is in mock mode; no trusted target SQL generated."),
                "unknown",
                null,
                retrievedIds,
                Map.of(
                    "real", false,
                    "retrieval", retrieval,
                    "pair", pair,
                    "stages", stages,
                    "warning", "Configure a real app.llm.api-key before using this endpoint for metrics."
                )
            ));
        }

        Map<String, Object> generated = generateMigrationJson(sourceSql, pair, retrieval, stages, retrievedIds);
        return ResponseEntity.ok(new MigrateResponse(
            stringValue(generated.get("target_sql")),
            stringList(generated.get("report_points")),
            nullableString(generated.get("risk_level")),
            nullableDouble(generated.get("confidence")),
            retrievedIds,
            Map.of(
                "real", true,
                "retrieval", retrieval,
                "pair", pair,
                "stages", stages,
                "llm_output", generated
            )
        ));
    }

    private AgentGraph buildGraph() {
        AgentGraph g = new AgentGraph();
        g.addNode("01-analyzer", new SchemaAnalyzerAgent(llm));
        g.addNode("02-retriever", new ContextRetrieverAgent(llm));
        g.addNode("03-reasoner", new SqlReasonerAgent(llm));
        g.addNode("04-patcher", new SqlPatcherAgent(llm));
        g.addNode("05-critic", new SqlCriticAgent(llm));
        g.addNode("06-reporter", new ReportSummarizerAgent(llm));
        g.addEdge("01-analyzer", ctx -> "02-retriever");
        g.addEdge("02-retriever", ctx -> "03-reasoner");
        g.addEdge("03-reasoner", ctx -> "04-patcher");
        g.addEdge("04-patcher", ctx -> "05-critic");
        g.addEdge("05-critic", ctx -> "06-reporter");
        g.addEdge("06-reporter", ctx -> null);
        g.entry("01-analyzer");
        return g;
    }

    private Map<String, Object> generateMigrationJson(
            String sourceSql,
            String pair,
            String retrieval,
            List<Map<String, Object>> stages,
            List<String> retrievedIds
    ) {
        String prompt = """
            You are a senior database migration agent. Convert the source SQL according to the dialect pair.
            Use the executed 6-stage AgentGraph context as supporting evidence, but do not copy any gold answer.
            Return strict JSON only with this schema:
            {"target_sql":"...","report_points":["..."],"risk_level":"low|medium|high","confidence":0.0}

            Dialect pair: %s
            Retrieval mode: %s
            Source SQL:
            %s

            Retrieved ids:
            %s

            AgentGraph stage summaries:
            %s
            """.formatted(pair, retrieval, sourceSql, retrievedIds, toJson(stages));
        String reply = llm.chat(prompt);
        return parseJsonObject(reply);
    }

    private Map<String, Object> parseJsonObject(String reply) {
        try {
            JsonNode node = mapper.readTree(extractJson(reply));
            return mapper.convertValue(node, new TypeReference<>() {});
        } catch (Exception e) {
            Map<String, Object> fallback = new LinkedHashMap<>();
            fallback.put("target_sql", "");
            fallback.put("report_points", List.of("LLM returned non-JSON output; result requires manual review."));
            fallback.put("risk_level", "high");
            fallback.put("confidence", null);
            fallback.put("parse_error", e.getMessage());
            fallback.put("raw_reply", reply);
            return fallback;
        }
    }

    private String extractJson(String reply) {
        if (reply == null) return "{}";
        int start = reply.indexOf('{');
        int end = reply.lastIndexOf('}');
        if (start >= 0 && end > start) {
            return reply.substring(start, end + 1);
        }
        return reply;
    }

    private Map<String, Object> stageSnapshot(AgentStep step) {
        Map<String, Object> s = new LinkedHashMap<>();
        s.put("stage", step.stage());
        s.put("agentName", step.agentName());
        s.put("status", step.status());
        s.put("elapsedMs", step.elapsedMs());
        s.put("model", step.model());
        s.put("confidence", step.confidence());
        return s;
    }

    private List<String> extractRetrievedIds(Object retrieved) {
        if (!(retrieved instanceof List<?> docs)) return List.of();
        List<String> ids = new ArrayList<>();
        for (Object doc : docs) {
            if (doc instanceof Map<?, ?> map && map.get("id") != null) {
                ids.add(String.valueOf(map.get("id")));
            }
        }
        return ids;
    }

    private String normalizeRetrieval(String retrieval) {
        if (retrieval == null || retrieval.isBlank()) return "full";
        String value = retrieval.trim();
        return RETRIEVAL_CHOICES.contains(value) ? value : "full";
    }

    private String sourceDialect(String pair) {
        return pair.contains("->") ? pair.split("->", 2)[0] : pair;
    }

    private String targetDialect(String pair) {
        return pair.contains("->") ? pair.split("->", 2)[1] : pair;
    }

    private String stringValue(Object value) {
        return value == null ? "" : String.valueOf(value);
    }

    private String nullableString(Object value) {
        return value == null ? null : String.valueOf(value);
    }

    private Double nullableDouble(Object value) {
        if (value instanceof Number n) return n.doubleValue();
        if (value == null) return null;
        try {
            return Double.parseDouble(String.valueOf(value));
        } catch (NumberFormatException e) {
            return null;
        }
    }

    private List<String> stringList(Object value) {
        if (!(value instanceof List<?> raw)) return List.of();
        return raw.stream().map(String::valueOf).toList();
    }

    private String toJson(Object value) {
        try {
            return mapper.writeValueAsString(value);
        } catch (Exception e) {
            return String.valueOf(value);
        }
    }

    public record MigrateRequest(String source_sql, String pair, String retrieval) {}

    public record MigrateResponse(
        String target_sql,
        List<String> report_points,
        String risk_level,
        Double confidence,
        List<String> retrieved_ids,
        Map<String, Object> raw
    ) {}
}
