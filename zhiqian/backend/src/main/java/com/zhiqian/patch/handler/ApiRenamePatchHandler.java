package com.zhiqian.patch.handler;

import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.ImportDeclaration;
import com.zhiqian.patch.diff.UnifiedDiffBuilder;
import com.zhiqian.patch.model.*;
import org.springframework.stereotype.Component;

import java.util.*;

@Component
public class ApiRenamePatchHandler implements PatchHandler {

    private static final Map<String, String> RENAME = Map.of(
        "javax.servlet", "jakarta.servlet",
        "javax.persistence", "jakarta.persistence",
        "javax.validation", "jakarta.validation",
        "javax.annotation", "jakarta.annotation"
    );

    @Override public String supportedCategory() { return "api_rename"; }
    @Override public boolean canHandle(RiskUnit u) { return supportedCategory().equals(u.getCategory()); }

    @Override
    public PatchResult generate(RiskUnit unit, EvidencePack pack) {
        String src = unit.getCodeFragment();
        CompilationUnit cu = StaticJavaParser.parse(src);
        int changed = 0;
        for (ImportDeclaration imp : cu.getImports()) {
            String name = imp.getNameAsString();
            for (var e : RENAME.entrySet()) {
                if (name.startsWith(e.getKey())) {
                    imp.setName(name.replaceFirst(e.getKey(), e.getValue()));
                    changed++;
                }
            }
        }
        String rewritten = cu.toString();
        return PatchResult.builder()
                .unitId(unit.getUnitId())
                .category("api_rename")
                .targetFile(unit.getTargetFile())
                .unifiedDiff(UnifiedDiffBuilder.build(unit.getTargetFile(), src, rewritten))
                .confidence(changed > 0 ? 0.95 : 0.0)
                .requiresHumanReview(changed == 0)
                .evidenceIds(unit.getEvidenceIds())
                .rationale("javax->jakarta imports rewrote: " + changed)
                .build();
    }
}
