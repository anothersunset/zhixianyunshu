package com.zhiqian.migrationtool;

import java.util.List;
import java.util.Map;

import org.springframework.stereotype.Component;

/**
 * v2-step-22: pgloader 适配。
 * pgloader 是 Common Lisp 写的高性能 ETL, MySQL/SQLite/MS-SQL/csv → PostgreSQL。
 * 对 openGauss (postgres 兼容) 也有效。吞吐远超 LLM, 不能处理复杂转译。
 */
@Component
public class PgloaderAdapter implements MigrationTool {
    @Override public String id() { return "pgloader"; }
    @Override public String displayName() { return "pgloader (community)"; }
    @Override public String description() {
        return "高吞吐 ETL, 三行 command 完成 MySQL→Postgres/openGauss 全量迁移。适底层结构直进 / 大表迁移。不能转译过程/触发器。";
    }
    @Override public List<String> supportedSources() { return List.of("mysql","sqlite","sqlserver","csv","db3"); }
    @Override public List<String> supportedTargets() { return List.of("postgres","opengauss"); }
    @Override public Map<String,Object> tradeoffs() {
        return Map.of(
            "strength", List.of("三行 command","上千万行吞吐","不需 GPU/LLM","实战 10+ 年"),
            "weakness", List.of("不会转译过程/触发器","不慍 Oracle","错误提示对初学者不友好"),
            "throughput", "高 (10K rows/s+)",
            "setup", "低 (docker run dimitri/pgloader)",
            "cost", "低 (开源免费)"
        );
    }
    @Override public double matchScore(String src, String tgt) {
        if (src == null || tgt == null) return 0.0;
        if (!supportedSources().contains(src.toLowerCase())) return 0.0;
        if (!supportedTargets().contains(tgt.toLowerCase())) return 0.0;
        // mysql → postgres/opengauss 是 pgloader 强项
        if ("mysql".equalsIgnoreCase(src)) return 0.90;
        return 0.65;
    }
}
