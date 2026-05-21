package com.zhiqian.ckg;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.security.test.context.support.WithMockUser;
import org.springframework.test.web.servlet.MockMvc;

import static org.hamcrest.Matchers.greaterThan;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * v2-step-17: CkgGraphController WebMvc 测试。
 * 验证 GET /api/ckg/graph 返 demo 图的 13 节点 + 10 边。
 */
@WebMvcTest(controllers = CkgGraphController.class)
@Import(CkgGraphControllerWebMvcTest.SecurityBypassConfig.class)
class CkgGraphControllerWebMvcTest {

    @Autowired MockMvc mvc;

    @Test
    @WithMockUser
    void graphReturnsDemoNodesAndEdges() throws Exception {
        mvc.perform(get("/api/ckg/graph").param("projectId", "1"))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$.code").value(0))
           .andExpect(jsonPath("$.data.projectId").value(1))
           .andExpect(jsonPath("$.data.demo").value(true))
           .andExpect(jsonPath("$.data.nodes.length()", greaterThan(10)))
           .andExpect(jsonPath("$.data.edges.length()", greaterThan(5)));
    }

    @Test
    @WithMockUser
    void graphWithDefaultProjectIdWorks() throws Exception {
        mvc.perform(get("/api/ckg/graph"))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$.data.projectId").value(1));
    }

    @TestConfiguration
    static class SecurityBypassConfig {
        // 避免引入 SecurityFilterChain bean; 依赖 Spring Security 默认 + @WithMockUser 即可。
    }
}
