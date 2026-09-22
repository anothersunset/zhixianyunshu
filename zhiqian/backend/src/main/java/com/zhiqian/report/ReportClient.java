package com.zhiqian.report;

import java.time.Duration;
import java.util.Map;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.web.client.ClientHttpRequestFactories;
import org.springframework.boot.web.client.ClientHttpRequestFactorySettings;
import org.springframework.http.MediaType;
import org.springframework.http.client.ClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

/**
 * v2-step-27: 代理 RAG /reports endpoint。
 */
@Component
public class ReportClient {

    private final RestClient rest;

    public ReportClient(@Value("${app.rag.base-url:http://localhost:8001}") String ragUrl) {
        this.rest = RestClient.builder()
            .baseUrl(ragUrl)
            .requestFactory(requestFactory())
            .build();
    }

    /** connect 5s / read 60s 超时，避免 RAG 卡死占用请求线程。 */
    static ClientHttpRequestFactory requestFactory() {
        return ClientHttpRequestFactories.get(
            ClientHttpRequestFactorySettings.DEFAULTS
                .withConnectTimeout(Duration.ofSeconds(5))
                .withReadTimeout(Duration.ofSeconds(60)));
    }

    public byte[] generatePdf(Map<String, Object> payload) {
        return rest.post()
                .uri("/reports/generate")
                .contentType(MediaType.APPLICATION_JSON)
                .body(payload)
                .retrieve()
                .body(byte[].class);
    }

    public Map<String, Object> status() {
        return rest.get().uri("/reports/status").retrieve().body(Map.class);
    }
}
