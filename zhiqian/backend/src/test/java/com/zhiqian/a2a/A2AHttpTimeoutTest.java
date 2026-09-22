package com.zhiqian.a2a;

import org.junit.jupiter.api.Test;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.core.task.SyncTaskExecutor;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.web.client.RestTemplate;

import java.lang.reflect.Field;

import static org.assertj.core.api.Assertions.assertThat;

class A2AHttpTimeoutTest {
    @Test
    void defaultConstructorAppliesConnectAndReadTimeoutsToRestTemplate() throws Exception {
        A2ATaskExecutor executor = new A2ATaskExecutor(
            new SyncTaskExecutor(), new RestTemplateBuilder(), "http://rag.internal:8001");

        Field restField = A2ATaskExecutor.class.getDeclaredField("rest");
        restField.setAccessible(true);
        RestTemplate rest = (RestTemplate) restField.get(executor);

        // classpath 无 Apache/Jetty HTTP 客户端，Boot 3.2 检测结果确定为 SimpleClientHttpRequestFactory；
        // Spring 6.1 该工厂只有 setter，超时值从私有字段读取
        assertThat(rest.getRequestFactory()).isInstanceOf(SimpleClientHttpRequestFactory.class);
        var factory = (SimpleClientHttpRequestFactory) rest.getRequestFactory();
        assertThat(ReflectionTestUtils.getField(factory, "connectTimeout")).isEqualTo(5000);
        assertThat(ReflectionTestUtils.getField(factory, "readTimeout")).isEqualTo(60000);
    }
}
