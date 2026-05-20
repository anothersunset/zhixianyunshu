package com.zhiqian.patch.handler;

import com.zhiqian.patch.diff.UnifiedDiffBuilder;
import com.zhiqian.patch.model.*;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import net.sf.jsqlparser.parser.CCJSqlParserUtil;
import net.sf.jsqlparser.statement.Statement;
import org.springframework.stereotype.Component;

import java.util.*;
import java.util.regex.*;

@Slf4j
@Component
@RequiredArgsConstructor
public class SqlDialectPatchHandler implements PatchHandler {

    private static final List<Rewrite> RULES = List.of(
        new Rewrite("(?i)\\bROWNUM\\s*<=?\\s*(\\d+)", "LIMIT $1",        "oracle.rownum -> dameng.limit"),
        new Rewrite("(?i)\\bSYSDATE\\b",               "CURRENT_TIMESTAMP","oracle.sysdate -> ansi"),
        new Rewrite("(?i)\\bNVL\\(",                   "COALESCE(",        "oracle.nvl -> ansi.coalesce"),
        new Rewrite("(?i)\\bDUAL\\b",                  "",                  "oracle.dual removed")
    );

    @Override public String supportedCategory() { return "sql_dialect"; }
    @Override public boolean canHandle(RiskUnit u) { return supportedCategory().equals(u.getCategory()); }

    @Override
    public PatchResult generate(RiskUnit unit, EvidencePack pack) {
        String original = unit.getCodeFragment();
        String rewritten = original;
        List<String> rationale = new ArrayList<>();

        for (Rewrite r : RULES) {
            Matcher m = r.pattern.matcher(rewritten);
            if (m.find()) {
                rewritten = m.replaceAll(r.replacement);
                rationale.add(r.desc);
            }
        }

        boolean parseOk = tryParse(rewritten);
        double confidence = parseOk ? 0.92 : 0.55;

        String diff = UnifiedDiffBuilder.build(
                unit.getTargetFile(), original, rewritten);

        return PatchResult.builder()
                .unitId(unit.getUnitId())
                .category("sql_dialect")
                .targetFile(unit.getTargetFile())
                .unifiedDiff(diff)
                .confidence(confidence)
                .requiresHumanReview(!parseOk)
                .evidenceIds(unit.getEvidenceIds())
                .rationale(String.join("; ", rationale))
                .build();
    }

    private boolean tryParse(String sql) {
        try { Statement s = CCJSqlParserUtil.parse(sql); return s != null; }
        catch (Exception e) { return false; }
    }

    private record Rewrite(Pattern pattern, String replacement, String desc) {
        Rewrite(String p, String r, String d) { this(Pattern.compile(p), r, d); }
    }
}
