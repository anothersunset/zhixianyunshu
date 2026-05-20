package com.zhiqian.analyzer.sql;

import com.github.javaparser.ast.expr.AnnotationExpr;
import com.zhiqian.analyzer.model.JavaResult;
import com.zhiqian.analyzer.model.SqlResult;
import com.zhiqian.analyzer.model.SqlResult.RawSql;
import lombok.SneakyThrows;
import org.springframework.stereotype.Component;

import javax.xml.parsers.DocumentBuilderFactory;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.stream.Stream;

@Component
public class SqlExtractor {

	private static final Set<String> MYBATIS_ANNO = Set.of("Select", "Insert", "Update", "Delete");

	@SneakyThrows
	public SqlResult extract(Path projectRoot, JavaResult java) {
		List<RawSql> list = new ArrayList<>();

		try (Stream<Path> walk = Files.walk(projectRoot)) {
			walk.filter(p -> p.toString().endsWith(".xml"))
				.filter(SqlExtractor::isMybatisXml)
				.forEach(p -> list.addAll(parseMybatisXml(p)));
		}

		for (var cu : java.compilationUnits()) {
			cu.findAll(AnnotationExpr.class).forEach(an -> {
				if (!MYBATIS_ANNO.contains(an.getNameAsString())) return;
				an.getChildNodes().forEach(c -> {
					String v = c.toString();
					if (v.contains("\"")) {
						String sql = stripQuotes(v);
						String owner = cu.getStorage().map(s -> s.getPath().toString()).orElse("?");
						list.add(new RawSql(sql, owner, an.getBegin().map(b -> b.line).orElse(-1), "annotation", false));
					}
				});
			});
		}
		return new SqlResult(list);
	}

	private static boolean isMybatisXml(Path p) {
		try { String s = Files.readString(p); return s.contains("mapper.dtd") || s.contains("<mapper "); }
		catch (Exception e) { return false; }
	}

	@SneakyThrows
	private List<RawSql> parseMybatisXml(Path p) {
		var db = DocumentBuilderFactory.newInstance();
		db.setNamespaceAware(false); db.setValidating(false);
		db.setFeature("http://apache.org/xml/features/nonvalidating/load-external-dtd", false);
		var doc = db.newDocumentBuilder().parse(p.toFile());
		List<RawSql> out = new ArrayList<>();
		for (String tag : new String[]{"select", "insert", "update", "delete"}) {
			var nodes = doc.getElementsByTagName(tag);
			for (int i = 0; i < nodes.getLength(); i++) {
				var n = nodes.item(i);
				String sql = n.getTextContent().trim();
				boolean dyn = sql.contains("${") || sql.contains("<if") || sql.contains("<foreach");
				out.add(new RawSql(sql, p.toString(), -1, "xml", dyn));
			}
		}
		return out;
	}

	private String stripQuotes(String s) {
		int a = s.indexOf('"'); int b = s.lastIndexOf('"');
		return (a >= 0 && b > a) ? s.substring(a + 1, b) : s;
	}
}
