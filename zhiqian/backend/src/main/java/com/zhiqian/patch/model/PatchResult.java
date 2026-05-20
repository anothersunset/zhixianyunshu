package com.zhiqian.patch.model;

import lombok.Builder;
import lombok.Data;
import java.util.List;

@Data
@Builder
public class PatchResult {
    private String unitId;
    private String category;
    private String targetFile;
    private String unifiedDiff;
    private double confidence;
    private boolean requiresHumanReview;
    private List<String> evidenceIds;
    private String rationale;
}
