package com.zhiqian.patch.model;

import lombok.Builder;
import lombok.Data;

import java.util.List;
import java.util.Map;

@Data
@Builder
public class EvidencePack {
    private String taskId;
    private List<RiskUnit> riskUnits;
    private Map<String, Object> evidenceById;
}
