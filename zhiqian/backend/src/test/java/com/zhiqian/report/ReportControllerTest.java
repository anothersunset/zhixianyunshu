package com.zhiqian.report;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import com.zhiqian.security.JwtService;

import java.util.Map;

import static org.mockito.ArgumentMatchers.anyMap;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * ReportController 代理行为测试：200 代理成功、RAG 不可达时 503 降级、PDF 附件头。
 */
@WebMvcTest(controllers = ReportController.class)
@AutoConfigureMockMvc(addFilters = false)
class ReportControllerTest {

    @Autowired MockMvc mvc;
    @MockBean ReportClient reportClient;
    @MockBean JwtService jwtService; // JwtAuthenticationFilter 在 WebMvc 切片内必需

    @Test
    void statusProxiesRagStatusMap() throws Exception {
        when(reportClient.status()).thenReturn(Map.of("rag", "up", "docs", 128));

        mvc.perform(get("/api/reports/status"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.code").value(0))
            .andExpect(jsonPath("$.data.rag").value("up"))
            .andExpect(jsonPath("$.data.docs").value(128));
    }

    @Test
    void statusDegradesToCode503WhenRagUnreachable() throws Exception {
        when(reportClient.status()).thenThrow(new RuntimeException("Connection refused"));

        mvc.perform(get("/api/reports/status"))
            .andExpect(status().isOk()) // Result.fail 保持 HTTP 200，业务码 503
            .andExpect(jsonPath("$.code").value(503))
            .andExpect(jsonPath("$.message").value("rag unreachable: Connection refused"));
    }

    @Test
    void generateReturnsPdfAttachmentWithProjectNamedFilename() throws Exception {
        byte[] pdf = "%PDF-1.4 fake-report-bytes".getBytes();
        when(reportClient.generatePdf(anyMap())).thenReturn(pdf);

        mvc.perform(post("/api/reports/generate")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"project_name\":\"demo-migration\"}"))
            .andExpect(status().isOk())
            .andExpect(content().contentType(MediaType.APPLICATION_PDF))
            .andExpect(header().string("Content-Disposition",
                org.hamcrest.Matchers.containsString("filename=\"migration-report-demo-migration.pdf\"")))
            .andExpect(content().bytes(pdf));
    }
}
