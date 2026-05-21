package com.zhiqian.report;

import java.util.Map;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

/**
 * v2-step-27: 代理 RAG /reports endpoint。
 */
@Component
public class ReportClient {

    private final RestClient rest;

    public ReportClient(@Value("${zhiqian.rag.base-url:http://localhost:8001}") String ragUrl) {
        this.rest = RestClient.builder().baseUrl(ragUrl).build();
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
