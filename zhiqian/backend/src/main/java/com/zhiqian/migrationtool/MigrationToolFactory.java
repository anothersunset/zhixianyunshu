package com.zhiqian.migrationtool;

import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

import org.springframework.stereotype.Component;

/**
 * v2-step-22: 工具选型工厂。依赖所有 MigrationTool bean,
 * recommend(src,tgt) 返按 matchScore 降序的列表。
 */
@Component
public class MigrationToolFactory {

    private final List<MigrationTool> tools;

    public MigrationToolFactory(List<MigrationTool> tools) {
        this.tools = List.copyOf(tools);
    }

    public List<MigrationTool> all() { return tools; }

    public MigrationTool byId(String id) {
        return tools.stream().filter(t -> t.id().equalsIgnoreCase(id)).findFirst()
                .orElseThrow(() -> new IllegalArgumentException("unknown migration tool: " + id));
    }

    public List<Map<String, Object>> recommend(String sourceDialect, String targetDialect) {
        return tools.stream()
                .map(t -> Map.<String,Object>of(
                    "id", t.id(),
                    "name", t.displayName(),
                    "description", t.description(),
                    "score", t.matchScore(sourceDialect, targetDialect),
                    "tradeoffs", t.tradeoffs()))
                .sorted(Comparator.comparingDouble((Map<String,Object> m) -> ((Number)m.get("score")).doubleValue()).reversed())
                .collect(Collectors.toList());
    }
}
