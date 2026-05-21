package com.zhiqian.cdc;

import java.util.List;
import java.util.Map;

import org.springframework.beans.factory.ObjectProvider;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.zhiqian.common.Result;

/**
 * v2-step-21: Debezium CDC 控制面 REST。
 * 未启 (app.cdc.enabled=false) 返 503 + 不依赖实例。
 */
@RestController
@RequestMapping("/api/cdc")
public class CdcController {

    private final ObjectProvider<CdcConnectClient> clientProvider;
    private final CdcProperties props;

    public CdcController(ObjectProvider<CdcConnectClient> clientProvider, CdcProperties props) {
        this.clientProvider = clientProvider;
        this.props = props;
    }

    private ResponseEntity<Result<Object>> guard() {
        if (!props.isEnabled()) {
            return ResponseEntity.status(503).body(
                Result.fail(503, "CDC 未启用, 请设 app.cdc.enabled=true 并起 docker compose --profile cdc up"));
        }
        return null;
    }

    @GetMapping("/connectors")
    public ResponseEntity<?> list() {
        ResponseEntity<Result<Object>> g = guard(); if (g != null) return g;
        return ResponseEntity.ok(Result.ok(clientProvider.getObject().listConnectors()));
    }

    @GetMapping("/connectors/{name}/status")
    public ResponseEntity<?> status(@PathVariable String name) {
        ResponseEntity<Result<Object>> g = guard(); if (g != null) return g;
        return ResponseEntity.ok(Result.ok(clientProvider.getObject().connectorStatus(name)));
    }

    @PostMapping("/connectors")
    public ResponseEntity<?> register(@RequestBody Map<String, Object> body) {
        ResponseEntity<Result<Object>> g = guard(); if (g != null) return g;
        return ResponseEntity.ok(Result.ok(clientProvider.getObject().registerConnector(body)));
    }

    @PostMapping("/connectors/{name}/restart")
    public ResponseEntity<?> restart(@PathVariable String name) {
        ResponseEntity<Result<Object>> g = guard(); if (g != null) return g;
        clientProvider.getObject().restart(name);
        return ResponseEntity.ok(Result.ok("restarted"));
    }

    @PostMapping("/connectors/{name}/pause")
    public ResponseEntity<?> pause(@PathVariable String name) {
        ResponseEntity<Result<Object>> g = guard(); if (g != null) return g;
        clientProvider.getObject().pause(name);
        return ResponseEntity.ok(Result.ok("paused"));
    }

    @PostMapping("/connectors/{name}/resume")
    public ResponseEntity<?> resume(@PathVariable String name) {
        ResponseEntity<Result<Object>> g = guard(); if (g != null) return g;
        clientProvider.getObject().resume(name);
        return ResponseEntity.ok(Result.ok("resumed"));
    }

    @DeleteMapping("/connectors/{name}")
    public ResponseEntity<?> delete(@PathVariable String name) {
        ResponseEntity<Result<Object>> g = guard(); if (g != null) return g;
        clientProvider.getObject().delete(name);
        return ResponseEntity.ok(Result.ok("deleted"));
    }
}
