package com.zhiqian.migration;

import com.zhiqian.llm.LlmClient;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.asyncDispatch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.request;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@ActiveProfiles("test")
@AutoConfigureMockMvc
class MigrationEvalControllerTest {

    @Autowired MockMvc mvc;
    @MockBean LlmClient llm;

    @Test
    void migrateRunsAgentGraphAndReturnsEvaluationShapeWhenRealLlm() throws Exception {
        when(llm.isReal()).thenReturn(true);
        when(llm.providerName()).thenReturn("deepseek");
        when(llm.reason(anyString())).thenReturn("reason output");
        String migrationJson = """
            {"target_sql":"SELECT COALESCE(name,'anonymous') FROM users WHERE deleted=0",
             "report_points":["IFNULL is equivalent to COALESCE"],
             "risk_level":"low",
             "confidence":0.72}
            """;
        when(llm.chat(anyString())).thenReturn(migrationJson);

        mvc.perform(post("/migrate")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"source_sql\":\"SELECT IFNULL(name,'anonymous') FROM users WHERE deleted=0\",\"pair\":\"mysql->opengauss\",\"retrieval\":\"full\"}"))
            .andExpect(request().asyncStarted())
            .andDo(result -> mvc.perform(asyncDispatch(result)))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.target_sql").value("SELECT COALESCE(name,'anonymous') FROM users WHERE deleted=0"))
            .andExpect(jsonPath("$.report_points[0]").value("IFNULL is equivalent to COALESCE"))
            .andExpect(jsonPath("$.retrieved_ids").isArray())
            .andExpect(jsonPath("$.retrieved_ids.length()").value(org.hamcrest.Matchers.greaterThan(0)))
            .andExpect(jsonPath("$.raw.real").value(true))
            .andExpect(jsonPath("$.raw.stages.length()").value(org.hamcrest.Matchers.greaterThan(0)));
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
            .andExpect(request().asyncStarted())
            .andDo(result -> mvc.perform(asyncDispatch(result)))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.target_sql").value(""))
            .andExpect(jsonPath("$.raw.real").value(false))
            .andExpect(jsonPath("$.raw.warning").exists())
            .andExpect(jsonPath("$.raw.stages.length()").value(org.hamcrest.Matchers.greaterThan(0)));
    }

    // ===== fast path（fast=true 且非 agent 模式）：跳过 AgentGraph，直接 chat 生成 =====

    @Test
    void fastPathMigratesViaDirectChatAndMarksFastInMeta() throws Exception {
        when(llm.isReal()).thenReturn(true);
        when(llm.providerName()).thenReturn("deepseek");
        String migrationJson = """
            {"target_sql":"SELECT COALESCE(name,'anonymous') FROM users WHERE deleted=0",
             "report_points":["IFNULL is equivalent to COALESCE"],
             "risk_level":"low",
             "confidence":0.81}
            """;
        when(llm.chat(anyString())).thenReturn(migrationJson);

        mvc.perform(post("/migrate")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"source_sql\":\"SELECT IFNULL(name,'anonymous') FROM users WHERE deleted=0\","
                    + "\"pair\":\"mysql->opengauss\",\"retrieval\":\"full\",\"fast\":true}"))
            .andExpect(request().asyncStarted())
            .andDo(result -> mvc.perform(asyncDispatch(result)))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.target_sql").value("SELECT COALESCE(name,'anonymous') FROM users WHERE deleted=0"))
            .andExpect(jsonPath("$.report_points[0]").value("IFNULL is equivalent to COALESCE"))
            .andExpect(jsonPath("$.risk_level").value("low"))
            .andExpect(jsonPath("$.raw.fast").value(true))
            .andExpect(jsonPath("$.raw.real").value(true))
            .andExpect(jsonPath("$.raw.retrieval").value("full"))
            .andExpect(jsonPath("$.raw.llm_output.target_sql").exists())
            // fast path 保留轻量检索用于 recall 评估（RAG 不可用时回退本地 mock KB）
            .andExpect(jsonPath("$.retrieved_ids").isArray())
            .andExpect(jsonPath("$.retrieved_ids.length()").value(org.hamcrest.Matchers.greaterThan(0)));
    }

    @Test
    void fastPathDegradesToUntrustedFallbackWhenLlmIsMock() throws Exception {
        when(llm.isReal()).thenReturn(false);
        when(llm.providerName()).thenReturn("mock");
        when(llm.chat(anyString())).thenReturn("mock chat");

        mvc.perform(post("/migrate")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"source_sql\":\"SELECT IFNULL(name,'anonymous') FROM users\",\"fast\":true}"))
            .andExpect(request().asyncStarted())
            .andDo(result -> mvc.perform(asyncDispatch(result)))
            .andExpect(status().isOk())
            // mock LLM 的非 JSON 输出 → parseFallback：不产出可信 SQL，标记 high 风险
            .andExpect(jsonPath("$.target_sql").value(""))
            .andExpect(jsonPath("$.risk_level").value("high"))
            .andExpect(jsonPath("$.raw.fast").value(true))
            .andExpect(jsonPath("$.raw.real").value(false));
    }

    @Test
    void fastPathDegradesToFallbackWhenChatThrows() throws Exception {
        when(llm.isReal()).thenReturn(true);
        when(llm.providerName()).thenReturn("deepseek");
        when(llm.chat(anyString())).thenThrow(new RuntimeException("connection reset"));

        mvc.perform(post("/migrate")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"source_sql\":\"SELECT IFNULL(name,'anonymous') FROM users\",\"fast\":true}"))
            .andExpect(request().asyncStarted())
            .andDo(result -> mvc.perform(asyncDispatch(result)))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.target_sql").value(""))
            .andExpect(jsonPath("$.risk_level").value("high"))
            .andExpect(jsonPath("$.report_points[0]").value("LLM 调用失败: connection reset"));
    }

    // ===== 错误路径 =====

    @Test
    void migrateRejectsBlankSourceSqlWith400() throws Exception {
        when(llm.isReal()).thenReturn(true);

        mvc.perform(post("/migrate")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"source_sql\":\"   \",\"pair\":\"mysql->opengauss\",\"fast\":true}"))
            .andExpect(request().asyncStarted())
            .andDo(result -> mvc.perform(asyncDispatch(result)))
            .andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.code").value(400))
            .andExpect(jsonPath("$.message").value("source_sql must not be blank"));
    }

    @Test
    void migrateRejectsMalformedJsonBodyWith400() throws Exception {
        mvc.perform(post("/migrate")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"source_sql\": not-json"))
            .andExpect(status().isBadRequest());
    }
}
