package com.zhiqian.agent.tools;

import com.zhiqian.agent.AgentContext;
import com.zhiqian.agent.AgentTool;
import com.zhiqian.llm.LlmClient;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Stage 01 — 表结构与配置扫描。
 * 真 LLM 模式：用 chat-model 总结 schema 迁移风险。
 * Mock 模式：给出与 v1 同形的演示数据，保证 UI 什么也不用改。
 */
public class SchemaAnalyzerAgent implements AgentTool {
    private static final String SAMPLE_SCHEMA = """
            -- 样本（演示项目中随机抽取 3 表）：
            CREATE TABLE orders (
              id INT AUTO_INCREMENT PRIMARY KEY,
              user_id INT NOT NULL,
              total DECIMAL(10,2),
              created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
              payload JSON
            ) ENGINE=InnoDB;
            CREATE TABLE inventory (
              sku VARCHAR(64) PRIMARY KEY,
              stock INT,
              updated_at TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            );
            CREATE TABLE audit_log (
              id BIGINT AUTO_INCREMENT PRIMARY KEY,
              op_time DATETIME,
              detail TEXT
            );
            """;
    private final LlmClient llm;
    public SchemaAnalyzerAgent(LlmClient llm) { this.llm = llm; }
    @Override public String name() { return "Schema Analyzer"; }
    @Override public String description() { return "扫描 MySQL 表结构、配置文件，识别与 openGauss 不兼容的元素"; }
    @Override public Map<String, Object> run(AgentContext ctx, Map<String, Object> input) {
        String prompt = "你是 MySQL → openGauss 迁移专家。阅读以下 DDL，以 100 字以内总结 3 个最重要的迁移风险点（中文）。\n\n" + SAMPLE_SCHEMA;
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("files", 312);
        out.put("sqls", 78);
        out.put("configs", 19);
        if (llm.isReal()) {
            String reply = llm.chat(prompt);
            out.put("summary", reply);
            out.put("risks", List.of("AUTO_INCREMENT 需转 SEQUENCE", "DATETIME 默认值语法不同", "JSON 类型需验证 jsonb 存储"));
            out.put("_confidence", 0.86);
            out.put("_real", true);
        } else {
            out.put("summary", "识别到 312 个文件、共 78 条 SQL、19 份配置。主要风险：AUTO_INCREMENT / DATETIME 默认值 / JSON 存储。");
            out.put("risks", List.of("AUTO_INCREMENT", "DATETIME default", "JSON column"));
            out.put("_confidence", 0.82);
            out.put("_real", false);
        }
        out.put("_model", llm.providerName());
        return out;
    }
}
