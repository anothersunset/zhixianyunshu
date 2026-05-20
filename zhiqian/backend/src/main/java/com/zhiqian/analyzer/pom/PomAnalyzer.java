package com.zhiqian.analyzer.pom;

import com.zhiqian.analyzer.model.PomResult;
import lombok.SneakyThrows;
import org.apache.maven.model.Dependency;
import org.apache.maven.model.Model;
import org.apache.maven.model.io.xpp3.MavenXpp3Reader;
import org.springframework.stereotype.Component;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.stream.Stream;

@Component
public class PomAnalyzer {

	/** 企业常见信创不兼容依赖：GAV 前缀匹配。 */
	private static final List<String> KNOWN_RISK_GA = List.of(
		"com.oracle.database.jdbc:ojdbc",
		"com.microsoft.sqlserver:mssql-jdbc",
		"net.sourceforge.jtds:jtds",
		"com.ibm.db2:db2jcc"
	);

	@SneakyThrows
	public PomResult analyze(Path projectRoot) {
		List<Model> models = new ArrayList<>();
		try (Stream<Path> walk = Files.walk(projectRoot)) {
			walk.filter(p -> p.getFileName().toString().equals("pom.xml"))
				.forEach(p -> models.add(read(p)));
		}
		List<Dependency> all = new ArrayList<>();
		for (Model m : models) all.addAll(m.getDependencies());

		List<PomResult.RiskDep> bad = new ArrayList<>();
		for (Dependency d : all) {
			String ga = d.getGroupId() + ":" + d.getArtifactId();
			boolean risk = KNOWN_RISK_GA.stream().anyMatch(ga::startsWith);
			if (risk) bad.add(new PomResult.RiskDep(ga, d.getVersion(), "closed-source DB driver"));
		}
		return new PomResult(all, bad, models);
	}

	@SneakyThrows
	private Model read(Path pom) {
		try (var in = Files.newInputStream(pom)) { return new MavenXpp3Reader().read(in); }
	}
}
