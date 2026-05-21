package com.zhiqian.report;

import java.util.Map;

import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.zhiqian.common.Result;

@RestController
@RequestMapping("/api/reports")
public class ReportController {
    private final ReportClient client;

    public ReportController(ReportClient client) { this.client = client; }

    @GetMapping("/status")
    public Result<Map<String, Object>> status() {
        try { return Result.ok(client.status()); }
        catch (Exception e) { return Result.fail(503, "rag unreachable: " + e.getMessage()); }
    }

    @PostMapping("/generate")
    public ResponseEntity<byte[]> generate(@RequestBody Map<String, Object> payload) {
        byte[] pdf = client.generatePdf(payload);
        HttpHeaders h = new HttpHeaders();
        h.setContentType(MediaType.APPLICATION_PDF);
        h.setContentDispositionFormData("attachment",
            "migration-report-" + payload.getOrDefault("project_name", "report") + ".pdf");
        return new ResponseEntity<>(pdf, h, org.springframework.http.HttpStatus.OK);
    }
}
