package com.zhiqian;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

/**
 * v2-step-17: Testcontainers 集成测试 - 在真实 PostgreSQL 16 上启动 Spring 上下文。
 *
 * 仅在设置环境变量 RUN_TESTCONTAINERS=true (并且 Docker 可用) 时执行,
 * 避免本地开发者无 Docker 环境时 mvn test 报错。
 * CI 可为主枝脚本设 RUN_TESTCONTAINERS=true 打开。
 */
@SpringBootTest
@Testcontainers
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@EnabledIfEnvironmentVariable(named = "RUN_TESTCONTAINERS", matches = "true")
class PostgresIntegrationTest {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine")
            .withDatabaseName("zhiqian")
            .withUsername("zhiqian")
            .withPassword("zhiqian");

    @DynamicPropertySource
    static void registerProps(DynamicPropertyRegistry r) {
        r.add("spring.datasource.url", postgres::getJdbcUrl);
        r.add("spring.datasource.username", postgres::getUsername);
        r.add("spring.datasource.password", postgres::getPassword);
        r.add("spring.flyway.enabled", () -> "true");
        // Temporal/Langfuse 仍保持关, LLM 走 mock
        r.add("app.temporal.enabled", () -> "false");
        r.add("app.langfuse.enabled", () -> "false");
        r.add("app.llm.api-key", () -> "");
    }

    @Test
    void contextLoadsWithRealPostgres() {
        // Flyway 迁移能跑, Spring bean 能装, 即证明产品镜像可用
    }
}
