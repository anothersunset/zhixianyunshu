package com.zhiqian.analyzer;

import com.zhiqian.analyzer.model.ProjectProfile;
import com.zhiqian.ckg.model.Ckg;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.stream.Collectors;

@Service
public class ProjectProfileService {

	public ProjectProfile summarize(Ckg ckg) {
		int files = ckg.countByKind("File");
		int classes = ckg.countByKind("Class");
		int methods = ckg.countByKind("Method");
		int sqls = ckg.countByKind("SQL");
		int cfgs = ckg.countByKind("ConfigKey");

		List<String> badDeps = ckg.nodes("Dependency").stream()
			.filter(n -> Boolean.TRUE.equals(n.attr("risk")))
			.map(n -> (String) n.attr("ga"))
			.collect(Collectors.toList());

		int oracleSqls = (int) ckg.nodes("SQL").stream()
			.filter(n -> "ORACLE".equals(n.attr("dialect")))
			.count();

		int encryptedKeys = (int) ckg.nodes("ConfigKey").stream()
			.filter(n -> Boolean.TRUE.equals(n.attr("encrypted")))
			.count();

		return ProjectProfile.builder()
			.files(files).classes(classes).methods(methods).sqls(sqls).configKeys(cfgs)
			.riskDependencies(badDeps).oracleSqlCount(oracleSqls).encryptedConfigKeys(encryptedKeys)
			.build();
	}
}
