package com.zhiqian.agent.tools;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.zhiqian.agent.AgentContext;
import com.zhiqian.agent.AgentTool;
import com.zhiqian.llm.LlmClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestTemplate;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.stream.Stream;

import org.yaml.snakeyaml.Yaml;

/**
 * Stage 02 - migration knowledge retrieval.
 *
 * Tries RAG service first (real retrieval via Qdrant + BGE-M3),
 * falls back to local mock KB if RAG is unavailable.
 */
public class ContextRetrieverAgent implements AgentTool {
    private static final Logger log = LoggerFactory.getLogger(ContextRetrieverAgent.class);

    // ── KB 加载：优先从统一 YAML 读取，失败回退到硬编码 ──
    private static final Path KB_DIR = resolveKbDir();
    private static final List<KbDoc> KB = loadKb();

    private static Path resolveKbDir() {
        String configured = System.getProperty("kb.yaml.path", "");
        if (!configured.isBlank()) {
            return Paths.get(configured);
        }
        // 默认路径：从 backend 工作目录向上找 kb/active/
        Path cwd = Paths.get(System.getProperty("user.dir", "."));
        for (int i = 0; i < 5; i++) {
            Path kb = cwd.resolve("kb/active");
            if (Files.isDirectory(kb)) {
                return kb;
            }
            cwd = cwd.getParent();
            if (cwd == null) break;
        }
        return Paths.get("kb/active"); // fallback for logging
    }

    @SuppressWarnings("unchecked")
    private static List<KbDoc> loadKb() {
        // 1. 尝试从统一 YAML 加载
        try {
            if (Files.isDirectory(KB_DIR)) {
                log.info("[ContextRetriever] Loading KB from YAML: {}", KB_DIR.toAbsolutePath());
                Yaml yaml = new Yaml();
                List<KbDoc> docs = new ArrayList<>();
                try (Stream<Path> files = Files.list(KB_DIR)) {
                    List<Path> sorted = files
                        .filter(f -> f.getFileName().toString().startsWith("kb-"))
                        .sorted()
                        .toList();
                    for (Path f : sorted) {
                        Map<String, Object> data = yaml.load(Files.readString(f));
                        List<Map<String, Object>> docList = (List<Map<String, Object>>) data.get("docs");
                        if (docList != null) {
                            for (Map<String, Object> d : docList) {
                                String id = (String) d.get("id");
                                String text = (String) d.get("text");
                                String title = text != null && text.length() > 80
                                    ? text.substring(0, 80) : (text != null ? text : "");
                                String terms = (String) d.getOrDefault("terms", "");
                                docs.add(new KbDoc(id, title, terms));
                            }
                        }
                    }
                }
                if (!docs.isEmpty()) {
                    log.info("[ContextRetriever] Loaded {} KB docs from YAML", docs.size());
                    return docs;
                }
            } else {
                log.warn("[ContextRetriever] KB YAML dir not found: {}", KB_DIR.toAbsolutePath());
            }
        } catch (Exception e) {
            log.warn("[ContextRetriever] Failed to load KB from YAML: {}", e.getMessage());
        }

        // 2. 回退到硬编码 KB（与 kb/active/*.yaml 保持同步）
        log.info("[ContextRetriever] Using hardcoded fallback KB");
        return List.of(
            doc("kb-syntax-identifier", "Identifier quoting", "backtick reserved keyword order identifier"),
            doc("kb-func-ifnull", "IFNULL / NVL to COALESCE", "ifnull coalesce"),
            doc("kb-type-autoincrement", "Auto increment mapping", "auto_increment autoincrement serial bigserial sequence nextval identity"),
            doc("kb-type-enum", "Enum type mapping", "enum"),
            doc("kb-type-decimal", "Decimal numeric mapping", "decimal numeric number precision scale"),
            doc("kb-func-dateformat", "Date formatting functions", "date_format to_char yyyy"),
            doc("kb-syntax-limit", "LIMIT offset syntax", "limit offset rownum"),
            doc("kb-func-groupconcat", "GROUP_CONCAT to STRING_AGG", "group_concat string_agg separator aggregate"),
            doc("kb-syntax-upsert", "Upsert syntax", "duplicate conflict excluded"),
            doc("kb-func-regexp", "Regular expression operator", "regexp regex regular expression match tilde"),
            doc("kb-func-nvl", "Oracle NVL mapping", "nvl coalesce oracle"),
            doc("kb-func-sysdate", "Oracle sysdate mapping", "sysdate current_timestamp current date now"),
            doc("kb-syntax-dual", "Oracle dual table", "dual"),
            doc("kb-syntax-rownum", "Oracle rownum limit", "rownum limit"),
            doc("kb-func-decode", "Oracle DECODE mapping", "decode case when oracle conditional"),
            doc("kb-join-outer", "Oracle outer join", "(+) outer"),
            doc("kb-func-substr", "SUBSTR / SUBSTRING mapping", "substr substring string slice")
        );
    }

    private final LlmClient llm;
    private final String ragUrl;
    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final RestTemplate REST;
    // RAG 结果缓存：避免同一 case 的 5 个模式重复查询 RAG
    private static final ConcurrentHashMap<String, CacheEntry> RAG_CACHE = new ConcurrentHashMap<>();
    private static final long CACHE_TTL_MS = 5 * 60 * 1000; // 5 分钟

    private record CacheEntry(List<Map<String, Object>> docs, long timestamp) {
        boolean expired() { return System.currentTimeMillis() - timestamp > CACHE_TTL_MS; }
    }

    static {
        SimpleClientHttpRequestFactory rf = new SimpleClientHttpRequestFactory();
        rf.setConnectTimeout(8000);   // 8s 连接超时
        rf.setReadTimeout(60000);     // 60s 读取超时（并发负载下 embedding 检索可能较慢）
        REST = new RestTemplate(rf);
    }

    public ContextRetrieverAgent(LlmClient llm) {
        this(llm, System.getenv().getOrDefault("APP_RAG_BASE_URL", "http://localhost:8001"));
    }

    public ContextRetrieverAgent(LlmClient llm, String ragUrl) {
        this.llm = llm;
        this.ragUrl = ragUrl;
    }

    @Override public String name() { return "Context Retriever"; }

    @Override public String description() { return "Retrieve migration KB snippets for the current SQL and dialect pair"; }

    @Override public Map<String, Object> run(AgentContext ctx, Map<String, Object> input) {
        String sourceSql = String.valueOf(ctx.state().getOrDefault("source_sql", ""));
        String pair = String.valueOf(ctx.state().getOrDefault("pair", ""));
        String retrieval = String.valueOf(ctx.state().getOrDefault("retrieval", "full"));
        String query = (sourceSql + " " + pair).toLowerCase(Locale.ROOT);

        // 尝试 RAG 服务真实检索
        log.info("[ContextRetriever] ragUrl={}, retrieval={}, query={}", ragUrl, retrieval, query.length() > 60 ? query.substring(0, 60) + "..." : query);
        List<Map<String, Object>> docs = tryRagRetrieve(query, retrieval);
        log.info("[ContextRetriever] RAG returned: {}", docs == null ? "null (fallback to mock)" : docs.size() + " docs");

        String model;
        if (docs != null && !docs.isEmpty()) {
            model = "rag-" + retrieval;
        } else {
            // RAG 不可用,降级到本地 mock
            Set<String> tokens = tokenize(query);
            docs = KB.stream()
                .map(doc -> scored(doc, query, tokens, retrieval))
                .filter(doc -> ((Double) doc.get("score")) > 0.0)
                .sorted(Comparator.<Map<String, Object>, Double>comparing(doc -> (Double) doc.get("score")).reversed())
                .limit(5)
                .toList();
            if (docs.isEmpty()) {
                docs = fallbackDocs(retrieval);
            }
            model = "mock-fallback";
        }

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("top_k", 5);
        out.put("top_n", docs.size());
        out.put("retrieval", retrieval);
        out.put("retrieved", docs);
        out.put("_confidence", 0.82);
        out.put("_model", model);
        out.put("_real", docs != null && !docs.isEmpty());
        return out;
    }

    /**
     * 调用 RAG /retrieve 端点进行真实检索。失败时返回 null。
     * 使用 Spring RestTemplate (HTTP/1.1) 替代 JDK HttpClient，避免 Uvicorn HTTP/2 body 丢失。
     * 内置 5 分钟 TTL 缓存，避免同一 case 的 5 个模式重复查询。
     */
    private List<Map<String, Object>> tryRagRetrieve(String query, String mode) {
        // 检查缓存
        String cacheKey = query + "|" + mode;
        CacheEntry cached = RAG_CACHE.get(cacheKey);
        if (cached != null && !cached.expired()) {
            log.info("[ContextRetriever] cache hit for key={}", cacheKey.length() > 60 ? cacheKey.substring(0, 60) + "..." : cacheKey);
            return cached.docs();
        }

        // 重试逻辑：Connection refused 时重试一次（RAG 可能正在重启）
        int maxAttempts = 2;
        for (int attempt = 0; attempt < maxAttempts; attempt++) {
        try {
            String jsonBody = String.format(
                Locale.ROOT,
                "{\"query\":\"%s\",\"top_k\":5,\"mode\":\"%s\"}",
                query.replace("\"", "\\\""), mode
            );
            log.info("[ContextRetriever] RAG request body: {}", jsonBody);

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            HttpEntity<String> entity = new HttpEntity<>(jsonBody, headers);

            ResponseEntity<String> resp = REST.postForEntity(ragUrl + "/retrieve", entity, String.class);
            int status = resp.getStatusCode().value();
            String responseBody = resp.getBody() != null ? resp.getBody() : "";
            log.info("[ContextRetriever] RAG HTTP status={}, bodyLen={}", status, responseBody.length());
            if (status != 200) {
                log.warn("[ContextRetriever] RAG returned non-200: {}, body: {}", status, responseBody.length() < 300 ? responseBody : responseBody.substring(0, 300));
                return null;
            }

            JsonNode root = MAPPER.readTree(responseBody);
            JsonNode items = root.get("items");
            if (items == null || !items.isArray() || items.isEmpty()) {
                return null;
            }
            List<Map<String, Object>> docs = new ArrayList<>();
            for (JsonNode item : items) {
                String id = item.has("id") ? item.get("id").asText(null) : null;
                if (id == null) continue;
                double score = item.has("score") ? item.get("score").asDouble(0.0) : 0.0;
                String text = item.has("text") ? item.get("text").asText(null) : null;
                Map<String, Object> doc = new LinkedHashMap<>();
                doc.put("id", id);
                doc.put("score", score);
                if (text != null) doc.put("title", text.length() > 80 ? text.substring(0, 80) + "..." : text);
                docs.add(doc);
            }
            List<Map<String, Object>> result = docs.isEmpty() ? null : docs;
            // 存入缓存
            if (result != null) {
                RAG_CACHE.put(cacheKey, new CacheEntry(result, System.currentTimeMillis()));
            }
            return result;
        } catch (Exception e) {
            boolean isConnRefused = e.getMessage() != null && e.getMessage().contains("Connection refused");
            if (isConnRefused && attempt < maxAttempts - 1) {
                log.warn("[ContextRetriever] RAG Connection refused (attempt {}/{}), 3s 后重试", attempt + 1, maxAttempts);
                try { Thread.sleep(3000); } catch (InterruptedException ie) { Thread.currentThread().interrupt(); return null; }
                continue;
            }
            log.warn("[ContextRetriever] RAG call failed: {}", e.getMessage());
            return null;
        }
        } // end for
        return null;
    }

    private static Map<String, Object> scored(KbDoc doc, String query, Set<String> tokens, String retrieval) {
        double score = 0.0;
        for (String term : doc.terms().split(" ")) {
            if (!term.isBlank() && matches(term, query, tokens)) {
                score += retrievalWeight(retrieval, term);
            }
        }
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("id", doc.id());
        row.put("score", Math.min(0.99, score));
        row.put("title", doc.title());
        return row;
    }

    private static Set<String> tokenize(String query) {
        Set<String> tokens = new HashSet<>();
        for (String token : query.split("[^a-z0-9_]+")) {
            if (!token.isBlank()) {
                tokens.add(token);
            }
        }
        if (query.contains("`")) tokens.add("backtick");
        if (query.contains("(+)")) tokens.add("(+)");
        return tokens;
    }

    private static boolean matches(String term, String query, Set<String> tokens) {
        if (term.contains("_") || term.matches("[a-z0-9]+")) {
            return tokens.contains(term);
        }
        return query.contains(term);
    }

    private static double retrievalWeight(String retrieval, String term) {
        return switch (retrieval) {
            case "bm25" -> term.length() >= 5 ? 0.35 : 0.12;
            case "vector" -> 0.28;
            case "vector_rerank" -> term.length() >= 4 ? 0.42 : 0.18;
            case "crag" -> term.length() >= 4 ? 0.48 : 0.2;
            case "full" -> term.length() >= 4 ? 0.55 : 0.25;
            default -> 0.3;
        };
    }

    private static List<Map<String, Object>> fallbackDocs(String retrieval) {
        List<Map<String, Object>> docs = new ArrayList<>();
        Set<String> fallbackTokens = tokenize("auto_increment serial ifnull coalesce on duplicate key update");
        docs.add(scored(doc("kb-type-autoincrement", "Auto increment mapping", "auto_increment serial sequence"), "", fallbackTokens, retrieval));
        docs.add(scored(doc("kb-func-ifnull", "IFNULL / NVL to COALESCE", "ifnull coalesce"), "", fallbackTokens, retrieval));
        docs.add(scored(doc("kb-syntax-upsert", "Upsert syntax", "on duplicate key update on conflict"), "", fallbackTokens, retrieval));
        return docs;
    }

    private static KbDoc doc(String id, String title, String terms) {
        return new KbDoc(id, title, terms);
    }

    private record KbDoc(String id, String title, String terms) {}
}
