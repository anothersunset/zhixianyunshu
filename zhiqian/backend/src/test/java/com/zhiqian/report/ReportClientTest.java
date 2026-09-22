package com.zhiqian.report;

import org.junit.jupiter.api.Test;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.test.util.ReflectionTestUtils;

import static org.assertj.core.api.Assertions.assertThat;

class ReportClientTest {
    @Test
    void buildsRequestFactoryWithConnectAndReadTimeouts() {
        var factory = ReportClient.requestFactory();

        // classpath 无 Apache/Jetty HTTP 客户端，Boot 3.2 检测结果确定为 SimpleClientHttpRequestFactory；
        // Spring 6.1 该工厂只有 setter，超时值从私有字段读取
        assertThat(factory).isInstanceOf(SimpleClientHttpRequestFactory.class);
        assertThat(ReflectionTestUtils.getField(factory, "connectTimeout")).isEqualTo(5000);
        assertThat(ReflectionTestUtils.getField(factory, "readTimeout")).isEqualTo(60000);
    }
}
