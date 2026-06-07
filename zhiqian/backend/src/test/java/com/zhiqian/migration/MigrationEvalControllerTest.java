package com.zhiqian.migration;

import com.zhiqian.llm.LlmClient;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
class MigrationEvalControllerTest {

    @Autowired MockMvc mvc;
    @MockBean LlmClient llm;

    @Test
    void migrateRunsAgentGraphAndReturnsEvaluationShapeWhenRealLlm() throws Exception {
        when(llm.isReal()).thenReturn(true);
        when(llm.providerName()).thenReturn("deepseek");
        when(llm.reason(anyString()))
            .thenReturn("rewrite IFNULL to COALESCE")
            .thenReturn("critic passed")
            .thenReturn("""
            {"target_sql":"SELECT COALESCE(name,'anonymous') FROM users WHERE deleted=0",
             "report_points":["IFNULL is equivalent to COALESCE"],
             "risk_level":"low",
             "confidence":0.72}
            """);
        when(llm.chat(anyString())).thenReturn("stage summary");

        mvc.perform(post("/migrate")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"source_sql\":\"SELECT IFNULL(name,'anonymous') FROM users WHERE deleted=0\",\"pair\":\"mysql->opengauss\",\"retrieval\":\"full\"}"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.target_sql").value("SELECT COALESCE(name,'anonymous') FROM users WHERE deleted=0"))
            .andExpect(jsonPath("$.report_points[0]").value("IFNULL is equivalent to COALESCE"))
            .andExpect(jsonPath("$.retrieved_ids[0]").value("kb-func-ifnull"))
            .andExpect(jsonPath("$.raw.real").value(true))
            .andExpect(jsonPath("$.raw.stages.length()").value(6));
    }

    @Test
    void migrateDoesNotEmitTrustedSqlWhenLlmIsMock() throws Exception {
        when(llm.isReal()).thenReturn(false);
        when(llm.providerName()).thenReturn("mock");
        when(llm.reason(anyString())).thenReturn("mock reason");
        when(llm.chat(anyString())).thenReturn("mock chat");

        mvc.perform(post("/api/migrate")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"source_sql\":\"SELECT 1\",\"pair\":\"mysql->postgresql\",\"retrieval\":\"bm25\"}"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.target_sql").value(""))
            .andExpect(jsonPath("$.raw.real").value(false))
            .andExpect(jsonPath("$.raw.warning").exists())
            .andExpect(jsonPath("$.raw.stages.length()").value(6));
    }
}
