package com.zhiqian.patch.handler;

import com.zhiqian.patch.diff.UnifiedDiffBuilder;
import com.zhiqian.patch.model.*;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.*;

@Slf4j
@Component
public class DependencyPatchHandler implements PatchHandler {

    // 由 GraphRAG REPLACES 路径填充，演示期 hardcode 兑底
    private static final Map<String, String> REPLACE_TABLE = Map.of(
        "com.oracle.database.jdbc:ojdbc11",         "com.dameng:DmJdbcDriver18:8.1.3.62",
        "mysql:mysql-connector-java",                "com.dameng:DmJdbcDriver18:8.1.3.62",
        "com.alibaba:druid",                          "com.alibaba:druid:1.2.23"
    );

    @Override public String supportedCategory() { return "dependency"; }
    @Override public boolean canHandle(RiskUnit u) { return supportedCategory().equals(u.getCategory()); }

    @Override
    public PatchResult generate(RiskUnit unit, EvidencePack pack) {
        String key = unit.getMeta().get("ga");
        String target = REPLACE_TABLE.get(key);
        if (target == null) {
            return PatchResult.builder()
                    .unitId(unit.getUnitId())
                    .category("dependency")
                    .confidence(0.0)
                    .requiresHumanReview(true)
                    .rationale("no replacement found for " + key)
                    .build();
        }

        String original = unit.getCodeFragment();
        String rewritten = rebuildPomDep(target);

        return PatchResult.builder()
                .unitId(unit.getUnitId())
                .category("dependency")
                .targetFile(unit.getTargetFile())
                .unifiedDiff(UnifiedDiffBuilder.build(unit.getTargetFile(), original, rewritten))
                .confidence(0.90)
                .requiresHumanReview(false)
                .evidenceIds(unit.getEvidenceIds())
                .rationale("GraphRAG REPLACES path: " + key + " -> " + target)
                .build();
    }

    private String rebuildPomDep(String gav) {
        String[] parts = gav.split(":");
        return String.format(
            "<dependency>%n  <groupId>%s</groupId>%n  <artifactId>%s</artifactId>%n  <version>%s</version>%n</dependency>",
            parts[0], parts[1], parts.length >= 3 ? parts[2] : "latest");
    }
}
