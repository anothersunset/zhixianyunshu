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
import com.zhiqian.agent.tools.FeatureScannerAgent;
import com.zhiqian.agent.tools.SqlCriticAgent;
import com.zhiqian.llm.LlmClient;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.ResponseEntity;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.context.request.async.DeferredResult;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;
import java.util.stream.Stream;

import org.yaml.snakeyaml.Yaml;

@RestController
public class MigrationEvalController {

    private static final Logger log = LoggerFactory.getLogger(MigrationEvalController.class);
    private static final List<String> RETRIEVAL_CHOICES = List.of("bm25", "vector", "vector_rerank", "crag", "full");
    private static final AtomicLong TASK_ID = new AtomicLong(90_000L);

    // ===== SQL 复杂度判断（轻量规则）—— 优先从 YAML 加载 =====

    @SuppressWarnings("unchecked")
    private static Map<String, List<String>> loadComplexityFromYaml() {
        Map<String, List<String>> result = new ConcurrentHashMap<>();
        try {
            Path dir = resolveDialectsDir();
            if (Files.isDirectory(dir)) {
                Yaml yaml = new Yaml();
                try (Stream<Path> files = Files.list(dir)) {
                    for (Path f : files.filter(p -> p.toString().endsWith(".yaml")).toList()) {
                        Map<String, Object> data = yaml.load(Files.readString(f));
                        String dialect = (String) data.get("name");
                        List<String> keywords = (List<String>) data.get("complexity_keywords");
                        if (dialect != null && keywords != null && !keywords.isEmpty()) {
                            result.put(dialect, keywords);
                            log.info("[MigrationEval] Loaded {} complexity keywords for dialect '{}'",
                                    keywords.size(), dialect);
                        }
                    }
                }
            }
        } catch (Exception e) {
            log.warn("[MigrationEval] Failed to load complexity keywords from YAML: {}", e.getMessage());
        }
        return result;
    }

    private static Path resolveDialectsDir() {
        String configured = System.getProperty("kb.yaml.path", "");
        if (!configured.isBlank()) return Paths.get(configured, "dialects");
        Path cwd = Paths.get(System.getProperty("user.dir", "."));
        for (int i = 0; i < 5; i++) {
            Path kb = cwd.resolve("kb/active/dialects");
            if (Files.isDirectory(kb)) return kb;
            cwd = cwd.getParent();
            if (cwd == null) break;
        }
        return Paths.get("kb/active/dialects");
    }

    private static final Map<String, List<String>> DIALECT_COMPLEXITY = loadComplexityFromYaml();

    /** 源方言复杂度关键词（从 YAML 加载，回退到 Oracle 硬编码） */
    private static final List<String> ORACLE_KEYWORDS = DIALECT_COMPLEXITY.getOrDefault("oracle", List.of(
        "decode(", "rownum", "(+)", "from dual", "sysdate", "nvl(", "nvl2(", "connect by", "start with"
    ));

    /** 复杂 SQL 特征关键词（通用标记 + 所有方言复杂度关键词合并） */
    private static final List<String> COMPLEX_KEYWORDS = buildComplexKeywords();

    private static List<String> buildComplexKeywords() {
        Set<String> all = new LinkedHashSet<>();
        all.add("with ");
        all.add("recursive");
        for (List<String> kws : DIALECT_COMPLEXITY.values()) {
            all.addAll(kws);
        }
        return List.copyOf(all);
    }

    /**
     * 判断 SQL 是否为复杂场景，决定使用 chat() 还是 reason()。
     * 评分维度：行数、JOIN 数、子查询、Oracle 特有语法、函数变换数量。
     */
    public static boolean isComplexSql(String sql, String pair) {
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
        boolean agentMode = req.isAgentMode();

        // Fast path: 跳过 AgentGraph，直接 chat 生成，但保留轻量检索用于 recall 评估
        if (fast && !agentMode) {
            AgentContext fastCtx = new AgentContext(TASK_ID.incrementAndGet(), 1L);
            fastCtx.state().put("source_sql", sourceSql);
            fastCtx.state().put("pair", pair);
            fastCtx.state().put("retrieval", retrieval);
            Object retrievedRaw = new ContextRetrieverAgent(llm).run(fastCtx, Map.of()).get("retrieved");
            List<String> fastRetrievedIds = extractRetrievedIds(retrievedRaw);
            String retrievedKnowledge = extractRetrievedText(retrievedRaw);
            Map<String, Object> generated = generateMigrationJsonFast(sourceSql, pair, retrieval, retrievedKnowledge, "");
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

        // Agent path: 完整 AgentGraph 流水线（条件路由 + 自纠正循环）
        log.info("[doMigrate] agent mode={}, pair={}, sql={}", agentMode, pair,
                sourceSql.length() > 80 ? sourceSql.substring(0, 80) + "..." : sourceSql);

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
        String featureHints = stringValue(ctx.state().getOrDefault("feature_hints", ""));
        @SuppressWarnings("unchecked")
        List<DialectFeatureScanner.DetectedFeature> scannedFeatures =
            ctx.state().get("features") instanceof List<?> l
                ? l.stream().filter(o -> o instanceof DialectFeatureScanner.DetectedFeature)
                    .map(o -> (DialectFeatureScanner.DetectedFeature) o).toList()
                : List.of();

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

        // Agent path: 复用 fast path 的 prompt 生成 SQL，但加 Critic 自纠正
        String targetSql = "";
        List<String> reportPoints = List.of();
        String riskLevel = "medium";
        Double confidence = null;
        if (agentMode) {
            // 优化：如果源 SQL 未检测到任何方言特征，直接作为目标 SQL 输出（无需 LLM）
            if (scannedFeatures.isEmpty() && (featureHints == null || featureHints.isBlank())) {
                log.info("[AgentGraph] No source-dialect features detected, source SQL is already target-compatible — skipping LLM");
                targetSql = sourceSql;
                reportPoints = List.of("No conversion needed: source SQL is already target-dialect compatible");
                riskLevel = "low";
                confidence = 1.0;
            } else {
                // 用 fast path 相同的 prompt 生成 SQL（注入规则扫描的特征提示）
                Map<String, Object> generated = generateMigrationJsonFast(sourceSql, pair, retrieval, retrievedKnowledge, featureHints);
                targetSql = stringValue(generated.get("target_sql"));
                reportPoints = stringList(generated.get("report_points"));
                riskLevel = nullableString(generated.get("risk_level"));
                confidence = nullableDouble(generated.get("confidence"));

                // 后处理：修正 LLM 顽固失败模式（prompt 无法纠正的模式）
                targetSql = fixupStubbornPatterns(targetSql, sourceSql);

                // SQL 语法验证（sqlglot）：检查生成的 SQL 在目标方言上是否语法正确
                String syntaxError = null;
                if (!targetSql.isBlank()) {
                    SqlSyntaxValidator.ValidationResult syntaxResult =
                        SqlSyntaxValidator.validate(targetSql, targetDialect(pair));
                    if (!syntaxResult.valid()) {
                        syntaxError = syntaxResult.error();
                        log.info("[AgentGraph] Syntax validation FAILED: {}", syntaxError);
                    } else {
                        log.info("[AgentGraph] Syntax validation PASSED (sqlglot/{})", targetDialect(pair));
                    }
                }

                // Critic Layer 1: 规则检查 — 生成的 SQL 是否还残留源方言特征？
                boolean ruleFailed = !ruleCheckPasses(targetSql, sourceDialect(pair), scannedFeatures);
                if (ruleFailed && !targetSql.isBlank()) {
                    log.info("[AgentGraph] Layer1 rule check FAILED: source features remain in target SQL, forcing correction");
                }

                // Critic Layer 2: LLM 语义评审
                boolean syntaxFailed = syntaxError != null;
                String critique = "";
                boolean needsCorrection = syntaxFailed || ruleFailed;
                try {
                    SqlCriticAgent critic = new SqlCriticAgent(llm);
                    Map<String, Object> criticInput = Map.of("patch_preview", targetSql);
                    Map<String, Object> criticResult = critic.run(ctx, criticInput);
                    String llmCritique = stringValue(criticResult.get("critique"));
                    boolean llmNeedsFix = Boolean.TRUE.equals(criticResult.get("needs_correction"));
                    critique = (syntaxFailed ? "SYNTAX_ERROR: " + syntaxError + "\n" : "")
                        + (ruleFailed ? "LAYER1_FAIL: residual source-dialect features detected in target SQL.\n" : "")
                        + llmCritique;
                    needsCorrection = syntaxFailed || ruleFailed || llmNeedsFix;
                } catch (Exception e) {
                    log.warn("[AgentGraph] Critic 执行失败，跳过评审: {}", e.getMessage());
                    critique = (syntaxFailed ? "SYNTAX_ERROR: " + syntaxError + "\n" : "")
                        + (ruleFailed ? "LAYER1_FAIL: residual source-dialect features detected in target SQL.\n" : "")
                        + "STATUS: CORRECT\nDETAIL: Critic 执行异常，跳过评审。";
                }
                log.info("[AgentGraph] Critic: needsCorrection={}, critique={}",
                        needsCorrection, critique.length() > 100 ? critique.substring(0, 100) + "..." : critique);

                // Critic 自纠正：如果评审认为需要修正，带 critique 重新生成
                if (needsCorrection) {
                    log.info("[AgentGraph] Critic found issues, re-generating with critique");
                    String critiquePrompt = """
                        You are a senior database migration agent. Convert the source SQL according to the dialect pair.
                        Use ONLY the Retrieved Knowledge below as reference for conversion rules. Do NOT guess or use external knowledge.
                        Return strict JSON only with this schema:
                        {"target_sql":"...","report_points":["..."],"risk_level":"low|medium|high","confidence":0.0}

                        === Retrieved Knowledge (retrieval mode: %s) ===
                        %s
                        %s
                        === Previous Critique (FIX THESE ISSUES) ===
                        %s

                        IMPORTANT — report_points requirements:
                        - List EVERY transformation applied, one per point.
                        - Format: "SOURCE_FEATURE → TARGET_FEATURE: brief reason".

                        Dialect pair: %s
                        Source SQL:
                        %s
                        """.formatted(retrieval, retrievedKnowledge, featureHints, critique, pair, sourceSql);
                    try {
                        String reply = llm.chat(critiquePrompt); // 修正也用 chat-model
                        Map<String, Object> corrected = parseJsonObject(reply);
                        if (!stringValue(corrected.get("target_sql")).isBlank()) {
                            targetSql = fixupStubbornPatterns(stringValue(corrected.get("target_sql")), sourceSql);
                            reportPoints = stringList(corrected.get("report_points"));
                            riskLevel = nullableString(corrected.get("risk_level"));
                            confidence = nullableDouble(corrected.get("confidence"));
                            log.info("[AgentGraph] Correction applied, new SQL generated");
                        }
                    } catch (Exception e) {
                        log.warn("[AgentGraph] Correction re-generation failed: {}", e.getMessage());
                    }
                }
            }
        } else {
            // 非 agent 模式：保留原有的 generateMigrationJson 逻辑
            Map<String, Object> generated = generateMigrationJson(sourceSql, pair, retrieval, stages, retrievedIds, retrievedKnowledge);
            targetSql = stringValue(generated.get("target_sql"));
            reportPoints = stringList(generated.get("report_points"));
            riskLevel = nullableString(generated.get("risk_level"));
            confidence = nullableDouble(generated.get("confidence"));
        }

        Map<String, Object> meta = new LinkedHashMap<>();
        meta.put("real", true);
        meta.put("retrieval", retrieval);
        meta.put("pair", pair);
        meta.put("agent", agentMode);
        meta.put("feature_count", scannedFeatures.size());
        meta.put("stages", stages);
        return ResponseEntity.ok(new MigrateResponse(
            targetSql,
            reportPoints,
            riskLevel,
            confidence,
            retrievedIds,
            meta
        ));
    }

    /** v4 AgentGraph: 规则扫描 + RAG 检索，均无 LLM 开销（扫描器纯规则）。SQL 生成和 Critic 在 controller 层。 */
    private AgentGraph buildGraph() {
        AgentGraph g = new AgentGraph();
        g.addNode("01-scanner", new FeatureScannerAgent());
        g.addNode("02-retriever", new ContextRetrieverAgent(llm));
        g.addEdge("01-scanner", ctx -> "02-retriever");
        g.entry("01-scanner");
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
        log.info("[AdaptiveLLM] pair={}, sql={}", pair, sourceSql.length() > 80 ? sourceSql.substring(0, 80) + "..." : sourceSql);
        String reply;
        try {
            reply = llm.chat(prompt); // 永远用 chat-model 生成，reasoner 留给 Critic 做跨模型评审
        } catch (Exception e) {
            log.error("[generateMigrationJson] LLM 调用失败, 返回 parseFallback: {}", e.getMessage());
            return parseFallback("LLM 调用失败: " + e.getMessage(), "", e.getMessage());
        }
        return parseJsonObject(reply);
    }


    private Map<String, Object> generateMigrationJsonFast(
            String sourceSql,
            String pair,
            String retrieval,
            String retrievedKnowledge,
            String featureHints
    ) {
        String hintsSection = (featureHints != null && !featureHints.isBlank())
            ? "\n" + featureHints + "\n" : "";
        String prompt = """
            You are a senior database migration agent. Convert the source SQL according to the dialect pair.
            Use ONLY the Retrieved Knowledge below as reference for conversion rules. Do NOT guess or use external knowledge.
            Return strict JSON only with this schema:
            {"target_sql":"...","report_points":["..."],"risk_level":"low|medium|high","confidence":0.0}

            === Retrieved Knowledge (retrieval mode: %s) ===
            %s
            %s
            IMPORTANT — report_points requirements:
            - List EVERY transformation applied, one per point. For a query with 3 changes, generate 3 report_points.
            - Even "no change needed" items (e.g. "|| operator works in both dialects") count as a point.
            - Format: "SOURCE_FEATURE → TARGET_FEATURE: brief reason".
            - Generate at least 1 report_point; for any query with multiple SQL constructs, generate one point per construct.
            IMPORTANT — conversion rules:
            - ONLY convert constructs listed in the Retrieved Knowledge or Detected Features above. Do NOT invent conversions.
            - If a construct is NOT listed as needing conversion, keep it AS-IS. Do not restructure or rewrite SQL that is already valid in the target dialect.
            - Do NOT wrap working queries in CTEs unless explicitly required by a detected feature.
            - A correlated subquery in UPDATE (SET col = (SELECT ... WHERE key = outer.key)) is VALID PostgreSQL — do NOT convert it to UPDATE...FROM.

            Dialect pair: %s
            Source SQL:
            %s
            """.formatted(retrieval, retrievedKnowledge, hintsSection, pair, sourceSql);
        log.info("[AdaptiveLLM] pair={}, sql={}", pair, sourceSql.length() > 80 ? sourceSql.substring(0, 80) + "..." : sourceSql);
        String reply;
        try {
            // 永远用 chat-model 生成，reasoner 留给 SqlCriticAgent 做跨模型评审
            reply = llm.chat(prompt);
        } catch (Exception e) {
            log.error("[generateMigrationJsonFast] LLM 调用失败, 返回 parseFallback: {}", e.getMessage());
            return parseFallback("LLM 调用失败: " + e.getMessage(), "", e.getMessage());
        }
        return parseJsonObject(reply);
    }

    /** 从 patch_preview 中提取干净的 SQL（去掉 markdown 代码块）。 */
    private String cleanSqlBlock(String raw) {
        if (raw == null || raw.isBlank()) return "";
        String cleaned = raw
            .replaceAll("(?s)```(?:sql)?\\s*\\n?", "")
            .replace("```", "")
            .trim();
        return cleaned;
    }

    /** Critic Layer 1: 规则检查 — 生成的 SQL 是否还残留源方言特征。 */
    @SuppressWarnings("unchecked")
    private static boolean ruleCheckPasses(String targetSql, String sourceDialect,
                                            List<DialectFeatureScanner.DetectedFeature> sourceFeatures) {
        if (targetSql == null || targetSql.isBlank() || sourceFeatures.isEmpty()) return true;
        List<DialectFeatureScanner.DetectedFeature> residual =
            DialectFeatureScanner.scan(targetSql, sourceDialect);
        // 只检查是否还残留需要移除的特征（如 DECODE, ROWNUM 等），不检查兼容特征
        for (var f : residual) {
            String cat = f.category();
            // 函数、语法类特征残留 → 肯定有问题
            if ("function".equals(cat) || "syntax".equals(cat) || "operator".equals(cat)
                || "pseudo-column".equals(cat)) {
                return false;
            }
        }
        return true;
    }

    /**
     * 修正 LLM 顽固失败模式：对已知的 prompt 无法纠正的模式做后处理。
     * 仅修正确定性的单一错误，不做启发式猜测。
     * @param sql 生成的 SQL
     * @param sourceSql 原始源 SQL（用于上下文感知修正）
     */
    private static String fixupStubbornPatterns(String sql, String sourceSql) {
        if (sql == null || sql.isBlank()) return sql;
        String fixed = sql;

        // Fix 1: MONTHS_BETWEEN day fraction — LLM insists on adding EXTRACT(DAY FROM ...)/N
        // 仅移除 day 分数部分，保留公式其余结构不变（不消费前后括号）
        fixed = fixed.replaceAll(
            "\\s*\\+\\s*\\(?\\s*EXTRACT\\s*\\(\\s*DAY\\s+FROM\\s+age\\s*\\([^)]+,[^)]+\\)\\s*\\)"
            + "(\\s*::\\s*numeric)?\\s*/\\s*\\d+(\\.\\d+)?",
            "");

        // Fix 1b: CONNECT BY lvl 起始值 — deepseek-chat 倾向用 1 AS lvl 而非 0
        fixed = fixed.replaceAll("\\b1\\s+AS\\s+lvl\\b", "0 AS lvl");

        // Fix 1d: 移除 MONTHS_BETWEEN 结果中多余的 AS months_between 别名
        fixed = fixed.replaceAll("(?i)\\bAS\\s+months_between\\b", "");

        // Fix 1e: ROW_NUMBER() + LIMIT 组合 → 简化为纯 LIMIT/OFFSET（recipe 明确禁止此组合）
        if (fixed.matches("(?s).*ROW_NUMBER\\s*\\(\\s*\\).*LIMIT.*")) {
            // 提取 LIMIT N OFFSET M 并移除 ROW_NUMBER()
            fixed = fixed.replaceAll("(?i),?\\s*ROW_NUMBER\\s*\\(\\s*\\)\\s+(?:AS\\s+)?\\w+\\s*,?", " ");
            fixed = fixed.replaceAll("\\s{2,}", " ").trim();
        }

        // Fix 2b: regexp_match (singular, without S) → REGEXP_MATCHES (plural)
        fixed = fixed.replaceAll("(?i)regexp_match\\s*\\(", "REGEXP_MATCHES(");

        // Fix 6: SYSDATE → CURRENT_DATE fix to CURRENT_TIMESTAMP + strip ::date cast
        if (sourceSql != null && sourceSql.toUpperCase().contains("SYSDATE")) {
            // SYSDATE is timestamp in Oracle; replace CURRENT_DATE with CURRENT_TIMESTAMP
            fixed = fixed.replaceAll("(?i)\\bCURRENT_DATE\\b(\\s*-\\s*INTERVAL)", "CURRENT_TIMESTAMP$1");
            // Remove unnecessary ::date cast
            fixed = fixed.replaceAll("\\)\\s*::\\s*date\\b", ")");
        }
        // 同时清理外层多余括号: (EXTRACT(YEAR FROM age(...)) * 12 + EXTRACT(MONTH FROM age(...)))
        fixed = fixed.replaceAll(
            "\\(\\s*(EXTRACT\\s*\\(\\s*YEAR\\s+FROM\\s+age\\s*\\([^)]+,[^)]+\\)\\s*\\)\\s*\\*\\s*12\\s*\\+\\s*EXTRACT\\s*\\(\\s*MONTH\\s+FROM\\s+age\\s*\\([^)]+,[^)]+\\)\\s*\\))\\s*\\)",
            "$1");

        // Fix 1c: MONTHS_BETWEEN → 手动年月日公式（deepseek-chat 不用 age()）→ 替换为 age 公式
        if (sourceSql != null && sourceSql.toUpperCase().contains("MONTHS_BETWEEN(")) {
            // 匹配模式: (EXTRACT(YEAR FROM c1) - EXTRACT(YEAR FROM c2)) * 12 + (EXTRACT(MONTH FROM c1) - EXTRACT(MONTH FROM c2)) [+ day fraction]
            // 注意：用 [^)]+ 匹配列名（不含空格和括号）
            java.util.regex.Pattern manualMb = java.util.regex.Pattern.compile(
                "\\(?\\s*EXTRACT\\s*\\(\\s*YEAR\\s+FROM\\s+([^)]+)\\s*\\)\\s*-\\s*EXTRACT\\s*\\(\\s*YEAR\\s+FROM\\s+([^)]+)\\s*\\)\\s*\\)?\\s*\\*\\s*12",
                java.util.regex.Pattern.CASE_INSENSITIVE);
            java.util.regex.Matcher mbM = manualMb.matcher(fixed);
            if (mbM.find()) {
                String c1 = mbM.group(1).trim();
                String c2 = mbM.group(2).trim();
                // 整个公式替换: 移除手动年月日计算，用 age() 公式
                fixed = fixed.replaceAll(
                    "\\(?\\s*EXTRACT\\s*\\(\\s*YEAR\\s+FROM\\s+[^)]+\\s*\\)\\s*-\\s*EXTRACT\\s*\\(\\s*YEAR\\s+FROM\\s+[^)]+\\s*\\)\\s*\\)?\\s*\\*\\s*12\\s*"
                    + "\\+\\s*\\(?\\s*EXTRACT\\s*\\(\\s*MONTH\\s+FROM\\s+[^)]+\\s*\\)\\s*-\\s*EXTRACT\\s*\\(\\s*MONTH\\s+FROM\\s+[^)]+\\s*\\)\\s*\\)?"
                    + "(?:\\s*\\+\\s*\\(?\\s*EXTRACT\\s*\\(\\s*DAY\\s+FROM\\s+[^)]+\\s*\\)\\s*-\\s*EXTRACT\\s*\\(\\s*DAY\\s+FROM\\s+[^)]+\\s*\\)\\s*\\)?\\s*/\\s*\\d+(\\.\\d+)?)?",
                    "EXTRACT(YEAR FROM age(" + c1 + ", " + c2 + ")) * 12 + EXTRACT(MONTH FROM age(" + c1 + ", " + c2 + "))");
            }
        }

        // Fix 2: REGEXP_SUBSTR → SUBSTRING(email FROM pattern) should be (REGEXP_MATCHES(email, pattern))[1]
        java.util.regex.Pattern subP = java.util.regex.Pattern.compile(
            "SUBSTRING\\s*\\(\\s*(\\S+)\\s+FROM\\s+('[^']*')\\s*\\)",
            java.util.regex.Pattern.CASE_INSENSITIVE);
        java.util.regex.Matcher m = subP.matcher(fixed);
        if (m.find()) {
            fixed = m.replaceAll("(REGEXP_MATCHES($1, $2))[1]");
        }

        // Fix 3: REGEXP_SUBSTR → split_part(col, delim, n) — LLM "shortcut" that ignores regex pattern
        // Extract original REGEXP_SUBSTR(col, 'pattern') from source and construct correct output
        if (sourceSql != null && !sourceSql.isBlank()) {
            java.util.regex.Pattern srcRegexp = java.util.regex.Pattern.compile(
                "REGEXP_SUBSTR\\s*\\(\\s*(\\S+)\\s*,\\s*('[^']*')\\s*\\)",
                java.util.regex.Pattern.CASE_INSENSITIVE);
            java.util.regex.Matcher srcM = srcRegexp.matcher(sourceSql);
            java.util.regex.Pattern splitPartP = java.util.regex.Pattern.compile(
                "split_part\\s*\\(\\s*\\S+\\s*,\\s*'[^']*'\\s*,\\s*\\d+\\s*\\)",
                java.util.regex.Pattern.CASE_INSENSITIVE);
            if (srcM.find() && splitPartP.matcher(fixed).find()) {
                // Replace split_part(...) with (REGEXP_MATCHES(col, pattern))[1]
                String col = srcM.group(1);
                String pattern = srcM.group(2);
                fixed = splitPartP.matcher(fixed).replaceAll("(REGEXP_MATCHES(" + col + ", " + pattern + "))[1]");
            }
        }

        return fixed;
    }

    /** 从 report_md 中提取报告要点（每行一个 "- " 开头）。 */
    private List<String> extractReportPoints(String reportMd) {
        if (reportMd == null || reportMd.isBlank()) return List.of();
        return reportMd.lines()
            .map(String::trim)
            .filter(l -> l.startsWith("- ") || l.startsWith("* "))
            .map(l -> l.substring(2).trim())
            .filter(l -> !l.isBlank())
            .toList();
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

    /** 通用 LLM 代理端点——供 Python 工具链（kb_generator/recipe_suggester）调用，复用后端的 LLM 认证配置。 */
    @PostMapping({"/chat", "/api/chat"})
    public ResponseEntity<Map<String, Object>> chat(@RequestBody ChatRequest req) {
        String reply = llm.chat(req.prompt());
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("reply", reply);
        return ResponseEntity.ok(result);
    }

    public record ChatRequest(String prompt) {}

    public record MigrateRequest(String source_sql, String pair, String retrieval, boolean fast, String mode) {
        public boolean isAgentMode() {
            return "agent".equals(mode);
        }
    }

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
