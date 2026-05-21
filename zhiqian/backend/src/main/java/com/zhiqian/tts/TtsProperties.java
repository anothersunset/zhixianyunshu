package com.zhiqian.tts;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * v2-step-26: TTS 配置。默 走 edge-tts CLI 代理, 不装时优雅 503。
 */
@Component
@ConfigurationProperties(prefix = "app.tts")
public class TtsProperties {
    private boolean enabled = false;
    private String engine = "edge-tts";
    private String voice = "zh-CN-XiaoxiaoNeural";
    private String rate = "+0%";
    private String volume = "+0%";
    private int timeoutSeconds = 20;

    public boolean isEnabled() { return enabled; }
    public void setEnabled(boolean enabled) { this.enabled = enabled; }
    public String getEngine() { return engine; }
    public void setEngine(String engine) { this.engine = engine; }
    public String getVoice() { return voice; }
    public void setVoice(String voice) { this.voice = voice; }
    public String getRate() { return rate; }
    public void setRate(String rate) { this.rate = rate; }
    public String getVolume() { return volume; }
    public void setVolume(String volume) { this.volume = volume; }
    public int getTimeoutSeconds() { return timeoutSeconds; }
    public void setTimeoutSeconds(int timeoutSeconds) { this.timeoutSeconds = timeoutSeconds; }
}
