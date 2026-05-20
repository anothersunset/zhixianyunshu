package com.zhiqian.analyzer.model;
import lombok.Builder;
import lombok.Value;
import java.util.List;

@Value @Builder
public class ProjectProfile {
	int files; int classes; int methods; int sqls; int configKeys;
	List<String> riskDependencies;
	int oracleSqlCount;
	int encryptedConfigKeys;
}
