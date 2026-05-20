package com.zhiqian.analyzer;

import com.zhiqian.analyzer.config.SpringConfigScanner;
import com.zhiqian.analyzer.java.JavaSourceAnalyzer;
import com.zhiqian.analyzer.model.*;
import com.zhiqian.analyzer.pom.PomAnalyzer;
import com.zhiqian.analyzer.sql.JSqlDialectDetector;
import com.zhiqian.analyzer.sql.SqlExtractor;
import com.zhiqian.ckg.CkgBuilder;
import com.zhiqian.ckg.model.Ckg;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.nio.file.Path;
import java.util.concurrent.CompletableFuture;

@Service
@RequiredArgsConstructor
public class ProjectAnalyzeOrchestrator {
	private final PomAnalyzer pomAnalyzer;
	private final JavaSourceAnalyzer javaAnalyzer;
	private final SqlExtractor sqlExtractor;
	private final JSqlDialectDetector dialectDetector;
	private final SpringConfigScanner configScanner;
	private final CkgBuilder ckgBuilder;
	private final ProjectProfileService profileService;

	public AnalyzeResult analyze(Path projectRoot) {
		long t0 = System.currentTimeMillis();

		var pomF = CompletableFuture.supplyAsync(() -> pomAnalyzer.analyze(projectRoot));
		var cfgF = CompletableFuture.supplyAsync(() -> configScanner.scan(projectRoot));
		var javaF = CompletableFuture.supplyAsync(() -> javaAnalyzer.analyze(projectRoot));

		PomResult pom = pomF.join();
		JavaResult java = javaF.join();
		ConfigResult cfg = cfgF.join();

		SqlResult sql = sqlExtractor.extract(projectRoot, java);
		DialectResult dialect = dialectDetector.detect(sql);

		Ckg ckg = ckgBuilder.build(pom, java, sql, dialect, cfg);
		ProjectProfile profile = profileService.summarize(ckg);

		long cost = System.currentTimeMillis() - t0;
		return new AnalyzeResult(ckg, profile, cost);
	}

	public record AnalyzeResult(Ckg ckg, ProjectProfile profile, long elapsedMs) {}
}
