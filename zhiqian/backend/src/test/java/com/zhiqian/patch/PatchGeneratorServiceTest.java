package com.zhiqian.patch;

import com.zhiqian.patch.diff.PatchAggregator;
import com.zhiqian.patch.model.*;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.*;

/**
 * PatchGeneratorService 单元测试
 * 测试 handler 分发、无匹配 handler、handler 异常等场景
 */
@ExtendWith(MockitoExtension.class)
class PatchGeneratorServiceTest {

    @Mock
    private PatchHandler handlerA;

    @Mock
    private PatchHandler handlerB;

    private PatchAggregator aggregator;

    private PatchGeneratorService service;

    @BeforeEach
    void setUp() {
        // 使用真实 PatchAggregator 进行集成验证
        aggregator = new PatchAggregator();
    }

    // ========== 辅助方法 ==========

    private RiskUnit riskUnit(String unitId, String category) {
        return RiskUnit.builder()
            .unitId(unitId)
            .category(category)
            .targetFile("src/Main.java")
            .codeFragment("old code")
            .evidenceIds(List.of("e1"))
            .meta(Map.of())
            .build();
    }

    private EvidencePack evidencePack(String taskId, List<RiskUnit> units) {
        return EvidencePack.builder()
            .taskId(taskId)
            .riskUnits(units)
            .evidenceById(Map.of())
            .build();
    }

    private PatchResult patchResult(String unitId, String category, double confidence) {
        return PatchResult.builder()
            .unitId(unitId)
            .category(category)
            .targetFile("src/Main.java")
            .unifiedDiff("--- a\n+++ b\n")
            .confidence(confidence)
            .requiresHumanReview(false)
            .evidenceIds(List.of("e1"))
            .rationale("auto fix")
            .build();
    }

    // ========== 正常分发 ==========

    @Nested
    @DisplayName("正常分发到匹配的 handler")
    class DispatchToMatchedHandler {

        @Test
        @DisplayName("单个 handler 匹配时正常生成 patch")
        void singleHandlerMatch() {
            RiskUnit unit = riskUnit("u1", "sql_dialect");
            PatchResult expected = patchResult("u1", "sql_dialect", 0.9);

            when(handlerA.canHandle(unit)).thenReturn(true);
            when(handlerA.generate(unit, evidencePack("t1", List.of(unit)))).thenReturn(expected);

            service = new PatchGeneratorService(List.of(handlerA), aggregator);
            EvidencePack pack = evidencePack("t1", List.of(unit));

            PatchSet result = service.generate(pack);

            assertNotNull(result);
            assertEquals(1, result.getTotal());
            assertEquals("t1", result.getTaskId());
            verify(handlerA).generate(unit, pack);
        }

        @Test
        @DisplayName("多个 handler 时分发到正确的 handler")
        void dispatchesToCorrectHandler() {
            RiskUnit unit = riskUnit("u1", "config");
            PatchResult expected = patchResult("u1", "config", 0.8);

            when(handlerA.canHandle(unit)).thenReturn(false);
            when(handlerB.canHandle(unit)).thenReturn(true);
            when(handlerB.generate(any(), any())).thenReturn(expected);

            service = new PatchGeneratorService(List.of(handlerA, handlerB), aggregator);
            EvidencePack pack = evidencePack("t1", List.of(unit));

            PatchSet result = service.generate(pack);

            assertNotNull(result);
            assertEquals(1, result.getTotal());
            verify(handlerA, never()).generate(any(), any());
            verify(handlerB).generate(eq(unit), any());
        }

        @Test
        @DisplayName("多个 risk unit 分别分发到不同 handler")
        void multipleUnitsDispatchToMultipleHandlers() {
            RiskUnit unit1 = riskUnit("u1", "sql_dialect");
            RiskUnit unit2 = riskUnit("u2", "config");
            PatchResult r1 = patchResult("u1", "sql_dialect", 0.9);
            PatchResult r2 = patchResult("u2", "config", 0.8);

            when(handlerA.canHandle(unit1)).thenReturn(true);
            when(handlerA.generate(eq(unit1), any())).thenReturn(r1);
            when(handlerA.canHandle(unit2)).thenReturn(false);
            when(handlerB.canHandle(unit2)).thenReturn(true);
            when(handlerB.generate(eq(unit2), any())).thenReturn(r2);

            service = new PatchGeneratorService(List.of(handlerA, handlerB), aggregator);
            EvidencePack pack = evidencePack("t1", List.of(unit1, unit2));

            PatchSet result = service.generate(pack);

            assertNotNull(result);
            assertEquals(2, result.getTotal());
        }
    }

    // ========== 无匹配 handler ==========

    @Nested
    @DisplayName("无匹配 handler")
    class NoMatchedHandler {

        @Test
        @DisplayName("无匹配 handler 时该 unit 被过滤，返回空 PatchSet")
        void noHandlerReturnsEmptyPatchSet() {
            RiskUnit unit = riskUnit("u1", "unknown_category");

            when(handlerA.canHandle(unit)).thenReturn(false);

            service = new PatchGeneratorService(List.of(handlerA), aggregator);
            EvidencePack pack = evidencePack("t1", List.of(unit));

            PatchSet result = service.generate(pack);

            assertNotNull(result);
            assertEquals(0, result.getTotal());
            assertTrue(result.getResults().isEmpty());
        }

        @Test
        @DisplayName("空 handler 列表时返回空 PatchSet")
        void emptyHandlerListReturnsEmptyPatchSet() {
            RiskUnit unit = riskUnit("u1", "sql_dialect");

            service = new PatchGeneratorService(List.of(), aggregator);
            EvidencePack pack = evidencePack("t1", List.of(unit));

            PatchSet result = service.generate(pack);

            assertNotNull(result);
            assertEquals(0, result.getTotal());
        }

        @Test
        @DisplayName("部分 unit 无匹配 handler 时只包含匹配的结果")
        void partialMatch() {
            RiskUnit unit1 = riskUnit("u1", "sql_dialect");
            RiskUnit unit2 = riskUnit("u2", "unknown");
            PatchResult r1 = patchResult("u1", "sql_dialect", 0.9);

            when(handlerA.canHandle(unit1)).thenReturn(true);
            when(handlerA.generate(eq(unit1), any())).thenReturn(r1);
            when(handlerA.canHandle(unit2)).thenReturn(false);

            service = new PatchGeneratorService(List.of(handlerA), aggregator);
            EvidencePack pack = evidencePack("t1", List.of(unit1, unit2));

            PatchSet result = service.generate(pack);

            assertNotNull(result);
            assertEquals(1, result.getTotal());
        }
    }

    // ========== handler 异常处理 ==========

    @Nested
    @DisplayName("handler 抛异常")
    class HandlerException {

        @Test
        @DisplayName("handler 抛异常时返回 requiresHumanReview=true 的结果")
        void handlerExceptionReturnsHumanReviewResult() {
            RiskUnit unit = riskUnit("u1", "sql_dialect");

            when(handlerA.canHandle(unit)).thenReturn(true);
            when(handlerA.generate(any(), any())).thenThrow(new RuntimeException("parse failed"));

            service = new PatchGeneratorService(List.of(handlerA), aggregator);
            EvidencePack pack = evidencePack("t1", List.of(unit));

            PatchSet result = service.generate(pack);

            assertNotNull(result);
            assertEquals(1, result.getTotal());

            PatchResult pr = result.getResults().get(0);
            assertTrue(pr.isRequiresHumanReview());
            assertEquals(0.0, pr.getConfidence());
            assertTrue(pr.getRationale().contains("handler error"));
            assertTrue(pr.getRationale().contains("parse failed"));
        }

        @Test
        @DisplayName("handler 异常不影响其他 unit 的正常处理")
        void handlerExceptionIsolated() {
            RiskUnit unit1 = riskUnit("u1", "sql_dialect");
            RiskUnit unit2 = riskUnit("u2", "config");
            PatchResult r2 = patchResult("u2", "config", 0.85);

            when(handlerA.canHandle(unit1)).thenReturn(true);
            when(handlerA.generate(eq(unit1), any())).thenThrow(new RuntimeException("boom"));
            when(handlerA.canHandle(unit2)).thenReturn(true);
            when(handlerA.generate(eq(unit2), any())).thenReturn(r2);

            service = new PatchGeneratorService(List.of(handlerA), aggregator);
            EvidencePack pack = evidencePack("t1", List.of(unit1, unit2));

            PatchSet result = service.generate(pack);

            assertNotNull(result);
            assertEquals(2, result.getTotal());

            // 第一个是异常结果，第二个是正常结果
            PatchResult failResult = result.getResults().stream()
                .filter(r -> "u1".equals(r.getUnitId()))
                .findFirst().orElseThrow();
            assertTrue(failResult.isRequiresHumanReview());

            PatchResult okResult = result.getResults().stream()
                .filter(r -> "u2".equals(r.getUnitId()))
                .findFirst().orElseThrow();
            assertFalse(okResult.isRequiresHumanReview());
        }
    }

    // ========== PatchAggregator 聚合 ==========

    @Nested
    @DisplayName("PatchAggregator 聚合验证")
    class Aggregation {

        @Test
        @DisplayName("聚合结果包含正确的统计信息")
        void aggregationStatistics() {
            RiskUnit unit1 = riskUnit("u1", "sql_dialect");
            RiskUnit unit2 = riskUnit("u2", "sql_dialect");
            PatchResult r1 = patchResult("u1", "sql_dialect", 0.9);
            PatchResult r2 = patchResult("u2", "sql_dialect", 0.8);

            when(handlerA.canHandle(any())).thenReturn(true);
            when(handlerA.generate(eq(unit1), any())).thenReturn(r1);
            when(handlerA.generate(eq(unit2), any())).thenReturn(r2);

            service = new PatchGeneratorService(List.of(handlerA), aggregator);
            EvidencePack pack = evidencePack("t1", List.of(unit1, unit2));

            PatchSet result = service.generate(pack);

            assertNotNull(result);
            assertEquals(2, result.getTotal());
            assertEquals(0.85, result.getAvgConfidence(), 0.001);
            assertEquals(0, result.getReviewRequired());
            assertNotNull(result.getByCategory());
            assertTrue(result.getByCategory().containsKey("sql_dialect"));
        }

        @Test
        @DisplayName("空 riskUnits 返回空 PatchSet")
        void emptyRiskUnitsReturnsEmptyPatchSet() {
            service = new PatchGeneratorService(List.of(handlerA), aggregator);
            EvidencePack pack = evidencePack("t1", List.of());

            PatchSet result = service.generate(pack);

            assertNotNull(result);
            assertEquals(0, result.getTotal());
        }
    }
}
