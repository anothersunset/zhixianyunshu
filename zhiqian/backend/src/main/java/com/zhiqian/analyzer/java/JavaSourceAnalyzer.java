package com.zhiqian.analyzer.java;

import com.github.javaparser.JavaParser;
import com.github.javaparser.ParserConfiguration;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.symbolsolver.JavaSymbolSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.CombinedTypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.JavaParserTypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.ReflectionTypeSolver;
import com.zhiqian.analyzer.model.JavaResult;
import lombok.SneakyThrows;
import org.springframework.stereotype.Component;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.stream.Stream;

@Component
public class JavaSourceAnalyzer {

	@SneakyThrows
	public JavaResult analyze(Path projectRoot) {
		CombinedTypeSolver solver = new CombinedTypeSolver();
		solver.add(new ReflectionTypeSolver());
		List<Path> srcDirs = locateSrcDirs(projectRoot);
		for (Path s : srcDirs) solver.add(new JavaParserTypeSolver(s));

		ParserConfiguration cfg = new ParserConfiguration()
			.setLanguageLevel(ParserConfiguration.LanguageLevel.JAVA_17)
			.setSymbolResolver(new JavaSymbolSolver(solver));
		JavaParser parser = new JavaParser(cfg);

		List<CompilationUnit> cus = new ArrayList<>();
		try (Stream<Path> walk = Files.walk(projectRoot)) {
			walk.filter(p -> p.toString().endsWith(".java"))
				.filter(p -> !p.toString().contains("/target/"))
				.forEach(p -> {
					try (var in = Files.newInputStream(p)) {
						var r = parser.parse(in);
						r.getResult().ifPresent(cu -> { cu.setStorage(p); cus.add(cu); });
					} catch (Exception ignore) {}
				});
		}
		return new JavaResult(cus);
	}

	@SneakyThrows
	private List<Path> locateSrcDirs(Path root) {
		List<Path> dirs = new ArrayList<>();
		try (Stream<Path> walk = Files.walk(root)) {
			walk.filter(Files::isDirectory)
				.filter(p -> p.endsWith(Path.of("src", "main", "java")))
				.forEach(dirs::add);
		}
		return dirs;
	}
}
