package com.zhiqian.observability;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * v2-step-08: Langfuse 配置绑定。
 *
 * <p>4 个字段:
 * <ul>
 *   <li>enabled: 总开关。即使 true,缺 keys 仍 auto-disabled。</li>
 *   <li>host: cloud.langfuse.com 或自托管 http://langfuse:3000</li>
 *   <li>publicKey / secretKey: 留空即 disabled。从环境变量读取,避免被误提交进仓。</li>
 * </ul>
 */
@ConfigurationProperties(prefix = "app.langfuse")
public class LangfuseProperties {

    private boolean enabled = true;
    private String host = "https://cloud.langfuse.com";
    private String publicKey = "";
    private String secretKey = "";

    public boolean isEnabled() { return enabled; }
    public void setEnabled(boolean enabled) { this.enabled = enabled; }

    public String getHost() { return host; }
    public void setHost(String host) { this.host = host; }

    public String getPublicKey() { return publicKey; }
    public void setPublicKey(String publicKey) { this.publicKey = publicKey; }

    public String getSecretKey() { return secretKey; }
    public void setSecretKey(String secretKey) { this.secretKey = secretKey; }
}
