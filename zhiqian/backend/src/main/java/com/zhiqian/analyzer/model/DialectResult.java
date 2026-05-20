package com.zhiqian.analyzer.model;
import java.util.List;
public record DialectResult(List<Item> items) {
	public record Item(SqlResult.RawSql raw, String dialect, List<String> badFeatures, boolean parseOk) {}
}
