package com.zhiqian.cdc;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * v2-step-21: Debezium Connect REST 客户端配置。
 * app.cdc.enabled=true 时 wire CdcController + CdcConnectClient。
 */
@ConfigurationProperties(prefix = "app.cdc")
public class CdcProperties {

    private boolean enabled = false;
    private String connectUrl = "http://localhost:8083";
    private int timeoutSeconds = 30;

    public boolean isEnabled() { return enabled; }
    public void setEnabled(boolean enabled) { this.enabled = enabled; }

    public String getConnectUrl() { return connectUrl; }
    public void setConnectUrl(String connectUrl) { this.connectUrl = connectUrl; }

    public int getTimeoutSeconds() { return timeoutSeconds; }
    public void setTimeoutSeconds(int timeoutSeconds) { this.timeoutSeconds = timeoutSeconds; }
}
