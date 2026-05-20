package com.zhiqian.patch.model;

import lombok.Builder;
import lombok.Data;

import java.util.List;
import java.util.Map;

@Data
@Builder
public class PatchSet {
    private String taskId;
    private int total;
    private double avgConfidence;
    private int reviewRequired;
    private List<PatchResult> results;
    private Map<String, List<PatchResult>> byCategory;
}
