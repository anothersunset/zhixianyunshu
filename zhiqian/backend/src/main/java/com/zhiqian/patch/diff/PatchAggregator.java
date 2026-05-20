package com.zhiqian.patch.diff;

import com.zhiqian.patch.model.*;
import org.springframework.stereotype.Component;

import java.util.*;
import java.util.stream.Collectors;

@Component
public class PatchAggregator {
    public PatchSet aggregate(String taskId, List<PatchResult> results) {
        double avgConf = results.stream().mapToDouble(PatchResult::getConfidence).average().orElse(0.0);
        long review = results.stream().filter(PatchResult::isRequiresHumanReview).count();

        Map<String, List<PatchResult>> byCategory = results.stream()
                .collect(Collectors.groupingBy(PatchResult::getCategory));

        return PatchSet.builder()
                .taskId(taskId)
                .total(results.size())
                .avgConfidence(avgConf)
                .reviewRequired((int) review)
                .results(results)
                .byCategory(byCategory)
                .build();
    }
}
