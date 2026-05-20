package com.zhiqian.patch;

import com.zhiqian.patch.model.*;
import com.zhiqian.patch.diff.PatchAggregator;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.*;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class PatchGeneratorService {

    private final List<PatchHandler> handlers;     // Spring 自动注入
    private final PatchAggregator aggregator;

    public PatchSet generate(EvidencePack pack) {
        log.info("[Patch] start task={}, units={}", pack.getTaskId(), pack.getRiskUnits().size());

        List<PatchResult> results = pack.getRiskUnits().stream()
                .map(unit -> dispatch(unit, pack))
                .filter(Objects::nonNull)
                .collect(Collectors.toList());

        return aggregator.aggregate(pack.getTaskId(), results);
    }

    private PatchResult dispatch(RiskUnit unit, EvidencePack pack) {
        for (PatchHandler h : handlers) {
            if (h.canHandle(unit)) {
                try {
                    return h.generate(unit, pack);
                } catch (Exception e) {
                    log.error("[Patch] handler={} unit={} failed",
                            h.getClass().getSimpleName(), unit.getUnitId(), e);
                    return PatchResult.builder()
                            .unitId(unit.getUnitId())
                            .category(unit.getCategory())
                            .confidence(0.0)
                            .requiresHumanReview(true)
                            .rationale("handler error: " + e.getMessage())
                            .build();
                }
            }
        }
        log.warn("[Patch] no handler for unit={}", unit.getUnitId());
        return null;
    }
}
