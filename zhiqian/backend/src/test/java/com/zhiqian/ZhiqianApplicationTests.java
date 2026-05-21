package com.zhiqian;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

/**
 * v2-step-17: Spring 上下文加载烟测。
 * 点亮绝大多数 Spring bean (Controller / Service / Config / Properties),
 * 是 JaCoCo 覆盖率的主力。 H2 + Flyway disabled, Temporal/Langfuse disabled, LLM=mock。
 */
@SpringBootTest
@ActiveProfiles("test")
class ZhiqianApplicationTests {

    @Test
    void contextLoads() {
        // 上下文能加载即表明所有必要 bean / Configuration / @ConditionalOnProperty
        // 不报错。 这单个测试抵千个微单测。
    }
}
