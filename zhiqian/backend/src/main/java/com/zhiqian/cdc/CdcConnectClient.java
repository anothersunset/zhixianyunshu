package com.zhiqian.cdc;

import java.time.Duration;
import java.util.List;
import java.util.Map;

import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

/**
 * v2-step-21: Debezium Connect REST 客户端。
 * 只包装常用几个 endpoint, 避免依赖 connect-api。
 */
@Component
public class CdcConnectClient {

    private final RestClient http;
    private final CdcProperties props;

    public CdcConnectClient(CdcProperties props) {
        this.props = props;
        this.http = RestClient.builder()
                .baseUrl(props.getConnectUrl())
                .defaultHeader("Accept", MediaType.APPLICATION_JSON_VALUE)
                .build();
    }

    @SuppressWarnings("unchecked")
    public List<String> listConnectors() {
        return http.get().uri("/connectors").retrieve().body(List.class);
    }

    public Map<String, Object> connectorStatus(String name) {
        return http.get().uri("/connectors/{n}/status", name)
                .retrieve()
                .onStatus(HttpStatusCode::isError, (req, res) -> {
                    throw new IllegalStateException("connect status " + res.getStatusCode());
                })
                .body(Map.class);
    }

    public Map<String, Object> registerConnector(Map<String, Object> body) {
        return http.post().uri("/connectors")
                .contentType(MediaType.APPLICATION_JSON)
                .body(body)
                .retrieve()
                .body(Map.class);
    }

    public void restart(String name) {
        http.post().uri("/connectors/{n}/restart", name).retrieve().toBodilessEntity();
    }

    public void pause(String name) {
        http.put().uri("/connectors/{n}/pause", name).retrieve().toBodilessEntity();
    }

    public void resume(String name) {
        http.put().uri("/connectors/{n}/resume", name).retrieve().toBodilessEntity();
    }

    public void delete(String name) {
        http.delete().uri("/connectors/{n}", name).retrieve().toBodilessEntity();
    }

    public Duration timeout() {
        return Duration.ofSeconds(props.getTimeoutSeconds());
    }
}
