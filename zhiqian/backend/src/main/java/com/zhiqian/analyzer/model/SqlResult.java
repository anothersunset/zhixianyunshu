package com.zhiqian.analyzer.model;
import java.util.List;
public record SqlResult(List<RawSql> sqls) {
	public record RawSql(String text, String origin, int line, String kind, boolean dynamic) {}
}
