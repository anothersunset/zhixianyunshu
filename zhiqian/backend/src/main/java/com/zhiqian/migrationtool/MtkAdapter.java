package com.zhiqian.migrationtool;

import java.util.List;
import java.util.Map;

import org.springframework.stereotype.Component;

/**
 * v2-step-22: MTK (Microsoft Toolkit 类产品) 适配。
 * 实际代表 SSMA (SQL Server Migration Assistant) / Migration Toolkit / Ora2Pg 等商业、梳理包。
 * Ora2Pg 在 Oracle → Postgres 是业界事实标准。
 */
@Component
public class MtkAdapter implements MigrationTool {
    @Override public String id() { return "mtk-ora2pg"; }
    @Override public String displayName() { return "Ora2Pg / SSMA (commercial-grade toolkit)"; }
    @Override public String description() {
        return "事实标准的 Oracle → Postgres 迁移套件, 含 PL/SQL → PL/pgSQL 转译器。适企业遗产上云 / 商业支持场景。";
    }
    @Override public List<String> supportedSources() { return List.of("oracle","sqlserver","sybase"); }
    @Override public List<String> supportedTargets() { return List.of("postgres","opengauss"); }
    @Override public Map<String,Object> tradeoffs() {
        return Map.of(
            "strength", List.of("Oracle PL/SQL 转译实战验证","含评估报告","商业支持 (SSMA)"),
            "weakness", List.of("配置复杂","转译质量依赖规则库","不能交互式修复"),
            "throughput", "中-高",
            "setup", "高 (需调 perl/Ora2Pg 配置文件)",
            "cost", "商业 SSMA 免费 / Ora2Pg 开源"
        );
    }
    @Override public double matchScore(String src, String tgt) {
        if (src == null || tgt == null) return 0.0;
        if (!supportedSources().contains(src.toLowerCase())) return 0.0;
        if (!supportedTargets().contains(tgt.toLowerCase())) return 0.0;
        if ("oracle".equalsIgnoreCase(src)) return 0.92;
        return 0.70;
    }
}
