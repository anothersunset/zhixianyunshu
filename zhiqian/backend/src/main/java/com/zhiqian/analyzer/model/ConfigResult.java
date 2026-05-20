package com.zhiqian.analyzer.model;
import java.util.List;
public record ConfigResult(List<Key> keys) {
	public record Key(String file, String key, String value, boolean sensitive, boolean encrypted) {}
}
