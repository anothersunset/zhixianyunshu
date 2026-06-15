package com.zhiqian.migration;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
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
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.ResponseEntity;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.context.request.async.DeferredResult;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicLong;

@RestController
public class MigrationEvalController {

    private static final Logger log = LoggerFactory.getLogger(MigrationEvalController.class);
    private static final List<String> RETRIEVAL_CHOICES = List.of("bm25", "vector", "vector_rerank", "crag", "full");
    private static final AtomicLong TASK_ID = new AtomicLong(90_000L);

    // ===== SQL 复杂度判断（轻量规则） =====

    /** Oracle 特有语法关键词 */
    private static final List<String> ORACLE_KEYWORDS = List.of(
        "decode(", "rownum", "(+)", "from dual", "sysdate", "nvl(", "nvl2(", "connect by", "start with"
    );

    /** 复杂 SQL 特征关键词 */
    private static final List<String> COMPLEX_KEYWORDS = List.of(
        "with ", "recursive", "connect by", "start with", "model ", "pivot(", "unpivot("
    );

    /**
     * 判断 SQL 是否为复杂场景，决定使用 chat() 还是 reason()。
     * 评分维度：行数、JOIN 数、子查询、Oracle 特有语法、函数变换数量。
     */
    static boolean isComplexSql(String sql, String pair) {
        if (sql == null || sql.isBlank()) return false;
        String lower = sql.toLowerCase();
        int score = 0;

        // 1. 行数（多语句/长 SQL）
        long lines = sql.lines().filter(l -> !l.isBlank()).count();
        if (lines > 15) score += 2;
        else if (lines > 8) score += 1;

        // 2. JOIN 数量
        long joinCount = lower.lines().filter(l -> l.matches(".*\\bjoin\\b.*")).count();
        if (joinCount >= 3) score += 3;
        else if (joinCount >= 2) score += 2;
        else if (joinCount >= 1) score += 1;

        // 3. 子查询（嵌套 SELECT）
        long subQueryCount = lower.chars().filter(ch -> ch == '(').count(); // 粗略估计
        long selectCount = lower.split("\\bselect\\b", -1).length - 1;
        if (selectCount >= 4) score += 3;
        else if (selectCount >= 2) score += 1;

        // 4. CTE / 复杂语法
        for (String kw : COMPLEX_KEYWORDS) {
            if (lower.contains(kw)) score += 2;
        }

        // 5. Oracle 特有语法（pair 含 oracle 时加分更高）
        boolean isOracle = pair != null && pair.contains("oracle");
        for (String kw : ORACLE_KEYWORDS) {
            if (lower.contains(kw)) {
                score += isOracle ? 2 : 1;
            }
        }

        // 6. 函数变换数量（需转译的函数）
        String[] funcPatterns = {"ifnull(", "date_format(", "group_concat(", "regexp ", "substr(",
                "nvl(", "decode(", "sysdate", "rownum"};
        long funcCount = 0;
        for (String f : funcPatterns) {
            if (lower.contains(f)) funcCount++;
        }
        if (funcCount >= 3) score += 2;
        else if (funcCount >= 2) score += 1;

        return score >= 6;
    }

    private final LlmClient llm;
    private final AgentRunner runner;
    private final ObjectMapper mapper;
    private final ThreadPoolTaskExecutor migrateExecutor;

    public MigrationEvalController(LlmClient llm, AgentRunner runner, ObjectMapper mapper,
                                   @Qualifier("migrateExecutor") ThreadPoolTaskExecutor migrateExecutor) {
        this.llm = llm;
        this.runner = runner;
        this.mapper = mapper;
        this.migrateExecutor = migrateExecutor;
    }

    @PostMapping({"/migrate", "/api/migrate"})
    public DeferredResult<ResponseEntity<MigrateResponse>> migrate(@RequestBody MigrateRequest req) {
        DeferredResult<ResponseEntity<MigrateResponse>> dr = new DeferredResult<>(300_000L);
        migrateExecutor.execute(() -> {
            try {
                ResponseEntity<MigrateResponse> resp = doMigrate(req);
                dr.setResult(resp);
            } catch (Exception e) {
                log.error("[migrate] 异步执行失败", e);
                dr.setErrorResult(e);
            }
        });
        return dr;
    }

    private ResponseEntity<MigrateResponse> doMigrate(MigrateRequest req) {
        String retrieval = normalizeRetrieval(req.retrieval());
        String pair = req.pair() == null || req.pair().isBlank() ? "mysql->opengauss" : req.pair();
        String sourceSql = req.source_sql() == null ? "" : req.source_sql();
        boolean fast = req.fast();

        // Fast path: 跳过 AgentGraph，直接 chat 生成，但保留轻量检索用于 recall 评估
        if (fast) {
            AgentContext fastCtx = new AgentContext(TASK_ID.incrementAndGet(), 1L);
            fastCtx.state().put("source_sql", sourceSql);
            fastCtx.state().put("pair", pair);
            fastCtx.state().put("retrieval", retrieval);
            Object retrievedRaw = new ContextRetrieverAgent(llm).run(fastCtx, Map.of()).get("retrieved");
            List<String> fastRetrievedIds = extractRetrievedIds(retrievedRaw);
            String retrievedKnowledge = extractRetrievedText(retrievedRaw);
            Map<String, Object> generated = generateMigrationJsonFast(sourceSql, pair, retrieval, retrievedKnowledge);
            return ResponseEntity.ok(new MigrateResponse(
                stringValue(generated.get("target_sql")),
                stringList(generated.get("report_points")),
                nullableString(generated.get("risk_level")),
                nullableDouble(generated.get("confidence")),
                fastRetrievedIds,
                Map.of(
                    "real", llm.isReal(),
                    "retrieval", retrieval,
                    "pair", pair,
                    "fast", true,
                    "llm_output", generated
                )
            ));
        }

        AgentContext ctx = new AgentContext(TASK_ID.incrementAndGet(), 1L);
        ctx.state().put("source_sql", sourceSql);
        ctx.state().put("pair", pair);
        ctx.state().put("retrieval", retrieval);
        ctx.state().put("sourceDialect", sourceDialect(pair));
        ctx.state().put("targetDialect", targetDialect(pair));

        List<Map<String, Object>> stages = new ArrayList<>();
        runner.run(buildGraph(), ctx, step -> stages.add(stageSnapshot(step)));
        List<String> retrievedIds = extractRetrievedIds(ctx.state().get("retrieved"));
        String retrievedKnowledge = extractRetrievedText(ctx.state().get("retrieved"));

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

        Map<String, Object> generated = generateMigrationJson(sourceSql, pair, retrieval, stages, retrievedIds, retrievedKnowledge);
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
            List<String> retrievedIds,
            String retrievedKnowledge
    ) {
        String prompt = """
            You are a senior database migration agent. Convert the source SQL according to the dialect pair.
            Use ONLY the Retrieved Knowledge below as reference for conversion rules. Do NOT guess or use external knowledge.
            Return strict JSON only with this schema:
            {"target_sql":"...","report_points":["..."],"risk_level":"low|medium|high","confidence":0.0}

            === Retrieved Knowledge (retrieval mode: %s) ===
            %s

            IMPORTANT — report_points requirements:
            - List EVERY transformation applied, one per point. For a query with 3 changes, generate 3 report_points.
            - Even "no change needed" items (e.g. "|| operator works in both dialects") count as a point.
            - Format: "SOURCE_FEATURE → TARGET_FEATURE: brief reason".
            - Generate at least 1 report_point; for any query with multiple SQL constructs, generate one point per construct.

            Dialect pair: %s
            Source SQL:
            %s

            Retrieved ids:
            %s

            AgentGraph stage summaries:
            %s
            """.formatted(retrieval, retrievedKnowledge, pair, sourceSql, retrievedIds, toJson(stages));
        boolean complex = isComplexSql(sourceSql, pair);
        log.info("[AdaptiveLLM] complex={}, pair={}, sql={}", complex, pair, sourceSql.length() > 80 ? sourceSql.substring(0, 80) + "..." : sourceSql);
        String reply = complex ? llm.reason(prompt) : llm.chat(prompt);
        return parseJsonObject(reply);
    }


    private Map<String, Object> generateMigrationJsonFast(
            String sourceSql,
            String pair,
            String retrieval,
            String retrievedKnowledge
    ) {
        String prompt = """
            You are a senior database migration agent. Convert the source SQL according to the dialect pair.
            Use ONLY the Retrieved Knowledge below as reference for conversion rules. Do NOT guess or use external knowledge.
            Return strict JSON only with this schema:
            {"target_sql":"...","report_points":["..."],"risk_level":"low|medium|high","confidence":0.0}

            === Retrieved Knowledge (retrieval mode: %s) ===
            %s

            IMPORTANT — report_points requirements:
            - List EVERY transformation applied, one per point. For a query with 3 changes, generate 3 report_points.
            - Even "no change needed" items (e.g. "|| operator works in both dialects") count as a point.
            - Format: "SOURCE_FEATURE → TARGET_FEATURE: brief reason".
            - Generate at least 1 report_point; for any query with multiple SQL constructs, generate one point per construct.

            Dialect pair: %s
            Source SQL:
            %s
            """.formatted(retrieval, retrievedKnowledge, pair, sourceSql);
        boolean complex = isComplexSql(sourceSql, pair);
        log.info("[AdaptiveLLM] complex={}, pair={}, sql={}", complex, pair, sourceSql.length() > 80 ? sourceSql.substring(0, 80) + "..." : sourceSql);
        String reply = complex ? llm.reason(prompt) : llm.chat(prompt);
        return parseJsonObject(reply);
    }

    private Map<String, Object> parseJsonObject(String reply) {
        try {
            JsonNode node = mapper.readTree(extractJson(reply));
            if (node == null || !node.isObject()) {
                return parseFallback("LLM returned JSON that is not an object.", reply, null);
            }
            return mapper.convertValue(node, new TypeReference<>() {});
        } catch (Exception e) {
            return parseFallback("LLM returned non-JSON output; result requires manual review.", reply, e.getMessage());
        }
    }

    private Map<String, Object> parseFallback(String message, String reply, String parseError) {
        Map<String, Object> fallback = new LinkedHashMap<>();
        fallback.put("target_sql", "");
        fallback.put("report_points", List.of(message));
        fallback.put("risk_level", "high");
        fallback.put("confidence", null);
        if (parseError != null) fallback.put("parse_error", parseError);
        fallback.put("raw_reply", reply);
        return fallback;
    }

    private String extractJson(String reply) {
        if (reply == null) return "{}";
        // Strip markdown code fences (```json ... ``` or ``` ... ```)
        String cleaned = reply.replaceAll("(?s)```(?:json)?\\s*\\n?(.*?)\\n?```", "$1").trim();
        int start = cleaned.indexOf('{');
        int end = cleaned.lastIndexOf('}');
        if (start >= 0 && end > start) {
            return cleaned.substring(start, end + 1);
        }
        return cleaned;
    }

    private Map<String, Object> stageSnapshot(AgentStep step) {
        Map<String, Object> s = new LinkedHashMap<>();
        s.put("stage", step.stage());
        s.put("agentName", step.agentName());
        s.put("status", step.status());
        s.put("elapsedMs", step.elapsedMs());
        s.put("model", step.model());
        s.put("confidence", step.confidence());
        // 携带 agent 的关键输出，供后续 generateMigrationJson 使用（截断过长字段）
        if (step.output() != null && !step.output().isEmpty()) {
            Map<String, Object> out = new LinkedHashMap<>();
            for (var e : step.output().entrySet()) {
                if (e.getKey().startsWith("_")) continue;
                Object val = e.getValue();
                if (val instanceof String sval && sval.length() > 500) {
                    val = sval.substring(0, 500) + "...(truncated)";
                }
                out.put(e.getKey(), val);
            }
            if (!out.isEmpty()) s.put("output", out);
        }
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

    /** 从检索结果中提取文档文本，格式化为 prompt 可用的知识段落。 */
    @SuppressWarnings("unchecked")
    private String extractRetrievedText(Object retrieved) {
        if (!(retrieved instanceof List<?> docs) || docs.isEmpty()) return "(no knowledge retrieved)";
        StringBuilder sb = new StringBuilder();
        int idx = 1;
        for (Object doc : docs) {
            if (doc instanceof Map) {
                Map<String, Object> map = (Map<String, Object>) doc;
                String id = String.valueOf(map.getOrDefault("id", "unknown"));
                Object titleObj = map.get("title");
                Object textObj = map.get("text");
                String text = textObj != null ? String.valueOf(textObj)
                            : titleObj != null ? String.valueOf(titleObj) : "";
                sb.append(idx++).append(". [").append(id).append("] ").append(text).append("\n");
            }
        }
        return sb.length() > 0 ? sb.toString() : "(no knowledge retrieved)";
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

    /** 代理 judge 调用——复用后端稳定的 RestClient，避免 Python 直连 DeepSeek API 挂起。 */
    @PostMapping({"/judge", "/api/judge"})
    public ResponseEntity<Map<String, Object>> judge(@RequestBody JudgeRequest req) {
        String prompt;
        if ("sql_equal".equals(req.type())) {
            String system = "你是资深数据库迁移评审。判断两段目标 SQL 在 " + req.target() + " 上是否语义等价，只输出 JSON。";
            String user = jsonObj("pred", req.pred()) + "\n" + jsonObj("gold", req.gold())
                + "\n输出 {\"equal\": true/false, \"reason\": \"...\"}";
            prompt = system + "\n\n" + user;
        } else {
            String system = "判断【标准要点】是否被【模型报告要点】覆盖，只输出 JSON。";
            String user = jsonObj("gold_point", req.gold_point()) + "\n"
                + jsonObj("pred_points", req.pred_points())
                + "\n输出 {\"covered\": true/false}";
            prompt = system + "\n\n" + user;
        }
        String reply = llm.chat(prompt);
        Map<String, Object> parsed = parseJsonObject(reply);
        return ResponseEntity.ok(parsed);
    }

    private static String jsonObj(String key, Object value) {
        try {
            return "{\"" + key + "\":" + new ObjectMapper().writeValueAsString(value) + "}";
        } catch (Exception e) {
            return "{}";
        }
    }

    public record MigrateRequest(String source_sql, String pair, String retrieval, boolean fast) {}

    public record JudgeRequest(String type, String pred, String gold, String target,
                               String gold_point, List<String> pred_points) {}

    public record MigrateResponse(
        String target_sql,
        List<String> report_points,
        String risk_level,
        Double confidence,
        List<String> retrieved_ids,
        Map<String, Object> raw
    ) {}
}
