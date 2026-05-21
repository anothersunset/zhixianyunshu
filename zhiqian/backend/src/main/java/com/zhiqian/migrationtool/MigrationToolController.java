package com.zhiqian.migrationtool;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.zhiqian.common.Result;

/**
 * v2-step-22: 迁移工具推荐 REST。
 * GET  /api/migration-tools                  列出所有工具
 * POST /api/migration-tools/recommend        body={sourceDialect,targetDialect} 推荐列表 (按 score 降序)
 */
@RestController
@RequestMapping("/api/migration-tools")
public class MigrationToolController {

    private final MigrationToolFactory factory;

    public MigrationToolController(MigrationToolFactory factory) {
        this.factory = factory;
    }

    @GetMapping
    public Result<List<Map<String,Object>>> list() {
        List<Map<String,Object>> data = factory.all().stream().map(t -> Map.<String,Object>of(
            "id", t.id(),
            "name", t.displayName(),
            "description", t.description(),
            "sources", t.supportedSources(),
            "targets", t.supportedTargets(),
            "tradeoffs", t.tradeoffs()
        )).collect(Collectors.toList());
        return Result.ok(data);
    }

    @PostMapping("/recommend")
    public Result<List<Map<String,Object>>> recommend(@RequestBody Map<String, Object> body) {
        String src = String.valueOf(body.getOrDefault("sourceDialect", "")).toLowerCase();
        String tgt = String.valueOf(body.getOrDefault("targetDialect", "")).toLowerCase();
        return Result.ok(factory.recommend(src, tgt));
    }
}
