package com.zhiqian.patch.model;

import lombok.Builder;
import lombok.Data;

import java.util.List;
import java.util.Map;

@Data
@Builder
public class RiskUnit {
    private String unitId;
    private String category;       // sql_dialect / dependency / config / api_rename / middleware / doc_only
    private String targetFile;
    private String codeFragment;
    private List<String> evidenceIds;
    private Map<String, String> meta;
}
