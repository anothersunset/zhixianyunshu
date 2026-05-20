package com.zhiqian.analyzer.config;

import com.zhiqian.analyzer.model.ConfigResult;
import lombok.SneakyThrows;
import org.springframework.stereotype.Component;
import org.yaml.snakeyaml.Yaml;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.stream.Stream;

@Component
public class SpringConfigScanner {

	private static final List<String> SENSITIVE_KEYS = List.of(
		"password", "secret", "token", "accesskey", "private-key"
	);

	@SneakyThrows
	public ConfigResult scan(Path projectRoot) {
		List<ConfigResult.Key> keys = new ArrayList<>();
		try (Stream<Path> walk = Files.walk(projectRoot)) {
			walk.filter(p -> {
				String n = p.getFileName().toString();
				return n.startsWith("application") && (n.endsWith(".yml") || n.endsWith(".yaml") || n.endsWith(".properties"));
			}).forEach(p -> keys.addAll(parse(p)));
		}
		return new ConfigResult(keys);
	}

	@SuppressWarnings("unchecked")
	@SneakyThrows
	private List<ConfigResult.Key> parse(Path p) {
		List<ConfigResult.Key> out = new ArrayList<>();
		if (p.toString().endsWith(".properties")) {
			var props = new Properties();
			try (var r = Files.newBufferedReader(p)) { props.load(r); }
			for (var e : props.entrySet()) addKey(out, p, e.getKey().toString(), e.getValue().toString());
		} else {
			Object doc = new Yaml().load(Files.newBufferedReader(p));
			flatten("", doc, (k, v) -> addKey(out, p, k, v));
		}
		return out;
	}

	private void addKey(List<ConfigResult.Key> out, Path p, String k, String v) {
		boolean sens = SENSITIVE_KEYS.stream().anyMatch(s -> k.toLowerCase().contains(s));
		boolean enc = sens && v != null && (v.startsWith("ENC(") || v.startsWith("{cipher}"));
		out.add(new ConfigResult.Key(p.toString(), k, v, sens, enc));
	}

	@SuppressWarnings("unchecked")
	private void flatten(String prefix, Object node, java.util.function.BiConsumer<String, String> sink) {
		if (node instanceof Map<?, ?> m) {
			for (var e : ((Map<String, Object>) m).entrySet()) {
				String nk = prefix.isEmpty() ? e.getKey() : prefix + "." + e.getKey();
				flatten(nk, e.getValue(), sink);
			}
		} else if (node instanceof List<?> l) {
			for (int i = 0; i < l.size(); i++) flatten(prefix + "[" + i + "]", l.get(i), sink);
		} else {
			sink.accept(prefix, node == null ? "" : node.toString());
		}
	}
}
