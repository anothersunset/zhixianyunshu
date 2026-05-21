package com.zhiqian.migrationtool;

import java.util.List;
import java.util.Map;

import org.springframework.stereotype.Component;

/**
 * v2-step-22: ZhiQian 自带 RAG+LLM 迁移流水线适配。
 * 复用 #3 6 Agent 流水线, 重量级但能处理表锁 / 过程 / 索引 / 存储过程 复杂转译。
 */
@Component
public class ZhiqianNativeAdapter implements MigrationTool {
    @Override public String id() { return "zhiqian-native"; }
    @Override public String displayName() { return "ZhiQian Native (LLM + RAG)"; }
    @Override public String description() {
        return "6 Agent 流水线 + BGE-M3+RRF 检索 + CRAG 修补, 处理表锁/过程/索引/存储过程转译。适用跨方言转译与复杂 SQL。";
    }
    @Override public List<String> supportedSources() { return List.of("mysql","oracle","sqlserver","db2","postgres"); }
    @Override public List<String> supportedTargets() { return List.of("opengauss","postgres","mysql"); }
    @Override public Map<String,Object> tradeoffs() {
        return Map.of(
            "strength", List.of("复杂 SQL 转译","上下文感知","可解释性","锐以适配 openGauss"),
            "weakness", List.of("需 GPU/API key","起动资源需求高","吞吐不及独立 ETL"),
            "throughput", "中 (LLM rate limit)",
            "setup", "中 (需 RAG/LLM stack)",
            "cost", "中 (LLM token)"
        );
    }
    @Override public double matchScore(String src, String tgt) {
        if (src == null || tgt == null) return 0.0;
        if (!supportedSources().contains(src.toLowerCase())) return 0.0;
        if (!supportedTargets().contains(tgt.toLowerCase())) return 0.0;
        // openGauss / 跨方言 = ZhiQian 优势
        if ("opengauss".equalsIgnoreCase(tgt)) return 0.95;
        if (!src.equalsIgnoreCase(tgt)) return 0.80;
        return 0.50;
    }
}
