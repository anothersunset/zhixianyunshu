package com.zhiqian.patch.model;

public interface PatchHandler {
    String supportedCategory();
    boolean canHandle(RiskUnit unit);
    PatchResult generate(RiskUnit unit, EvidencePack pack);
}
