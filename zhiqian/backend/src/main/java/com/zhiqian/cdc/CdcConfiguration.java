package com.zhiqian.cdc;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * v2-step-21: CDC 模块物件装配。
 * 仅在 app.cdc.enabled=true 时 wire CdcConnectClient, 否则 controller 中 guard 返 503。
 */
@Configuration
@EnableConfigurationProperties(CdcProperties.class)
public class CdcConfiguration {

    @Bean
    @ConditionalOnProperty(prefix = "app.cdc", name = "enabled", havingValue = "true")
    public CdcConnectClient cdcConnectClient(CdcProperties props) {
        return new CdcConnectClient(props);
    }
}
