package com.zhiqian.observability;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Configuration;

/**
 * v2-step-08: 启用 LangfuseProperties 配置绑定。
 */
@Configuration
@EnableConfigurationProperties(LangfuseProperties.class)
public class LangfuseConfig {
}
