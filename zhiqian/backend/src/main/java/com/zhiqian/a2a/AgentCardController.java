package com.zhiqian.a2a;

import java.util.List;
import java.util.Map;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * v2-step-24: A2A AgentCard。
 * 遵 Google A2A spec 0.2.x: GET /.well-known/agent.json
 * 其他 agent (Claude, GPT, custom) 看到 card 后就能发 task 过来。
 */
@RestController
public class AgentCardController {

    @Value("${zhiqian.a2a.base-url:http://localhost:8080}") private String baseUrl;

    @GetMapping(value = "/.well-known/agent.json", produces = MediaType.APPLICATION_JSON_VALUE)
    public Map<String, Object> card() {
        return Map.of(
            "name", "ZhiQian YunShu",
            "description", "智迁云枢: 企业级智能数据库迁移与 SQL 转译 agent。支持 mysql/oracle/sqlserver/db2 → openGauss/postgres。",
            "url", baseUrl + "/a2a",
            "version", "2.0.0",
            "capabilities", Map.of(
                "streaming", true,
                "pushNotifications", false,
                "stateTransitionHistory", true
            ),
            "defaultInputModes", List.of("text/plain", "application/json"),
            "defaultOutputModes", List.of("text/plain", "application/json"),
            "skills", List.of(
                Map.of(
                    "id", "sql.transpile",
                    "name", "SQL 转译",
                    "description", "将 SQL 从源方言转译到目标方言。输入 source_sql/source_dialect/target_dialect。",
                    "tags", List.of("sql","transpile","migration"),
                    "examples", List.of("帮我把 SELECT IFNULL(a,b) FROM t LIMIT 5,10 转为 openGauss")
                ),
                Map.of(
                    "id", "sql.explain",
                    "name", "SQL 变动说明",
                    "description", "结构化解释 SQL 转译后的变更、风险与修复建议。",
                    "tags", List.of("explain","risk"),
                    "examples", List.of("这条 SQL 迁到 openGauss 会有什么变动?")
                ),
                Map.of(
                    "id", "migration.plan",
                    "name", "迁移计划生成",
                    "description", "为数据库生成迁移分阶段计划、工具选型、风险评价。",
                    "tags", List.of("planning","strategy"),
                    "examples", List.of("Oracle 19c HR → openGauss 5.0 怎么做?")
                ),
                Map.of(
                    "id", "schema.analyze",
                    "name", "表结构分析",
                    "description", "分析 DDL 获取 columns/indexes/constraints + 迁移风险。",
                    "tags", List.of("schema","ddl"),
                    "examples", List.of("看看这个 CREATE TABLE 迁 openGauss 有哪些坎")
                )
            )
        );
    }
}
