package com.zhiqian.analyzer.model;

import java.util.List;

public record PomResult(
	List<org.apache.maven.model.Dependency> dependencies,
	List<RiskDep> riskDeps,
	List<org.apache.maven.model.Model> models
) {
	public record RiskDep(String ga, String version, String reason) {}
}
