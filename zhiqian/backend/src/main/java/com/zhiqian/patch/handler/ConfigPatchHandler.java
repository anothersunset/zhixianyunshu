package com.zhiqian.patch.handler;

import com.zhiqian.patch.diff.UnifiedDiffBuilder;
import com.zhiqian.patch.model.*;
import org.springframework.stereotype.Component;

import java.util.*;

@Component
public class ConfigPatchHandler implements PatchHandler {

    @Override public String supportedCategory() { return "config"; }
    @Override public boolean canHandle(RiskUnit u) { return supportedCategory().equals(u.getCategory()); }

    @Override
    public PatchResult generate(RiskUnit unit, EvidencePack pack) {
        String key = unit.getMeta().getOrDefault("key", "");
        String original = unit.getCodeFragment();
        String rewritten = original;
        List<String> notes = new ArrayList<>();

        if (key.contains("datasource.url")) {
            rewritten = original
                .replaceAll("jdbc:oracle:thin:@//?([^:/]+):(\\d+)[:/]([\\w]+)",
                            "jdbc:dm://$1:$2?schema=$3")
                .replaceAll("jdbc:mysql://([^?]+).*", "jdbc:dm://$1");
            notes.add("jdbc url -> dm");
        }
        if (key.contains("driver-class-name")) {
            rewritten = rewritten.replaceAll(
                "(oracle\\.jdbc\\.OracleDriver|com\\.mysql\\.cj\\.jdbc\\.Driver)",
                "dm.jdbc.driver.DmDriver");
            notes.add("driver class -> dm");
        }
        if (unit.getMeta().getOrDefault("sensitive", "false").equals("true")) {
            rewritten = rewritten.replaceAll("(password\\s*:\\s*)[^\\s#]+", "$1${DB_PASSWORD}");
            notes.add("plaintext -> env placeholder");
        }

        return PatchResult.builder()
                .unitId(unit.getUnitId())
                .category("config")
                .targetFile(unit.getTargetFile())
                .unifiedDiff(UnifiedDiffBuilder.build(unit.getTargetFile(), original, rewritten))
                .confidence(0.93)
                .requiresHumanReview(false)
                .evidenceIds(unit.getEvidenceIds())
                .rationale(String.join("; ", notes))
                .build();
    }
}
