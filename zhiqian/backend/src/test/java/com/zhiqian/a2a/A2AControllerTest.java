package com.zhiqian.a2a;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.Map;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.web.client.RestTemplate;

/**
 * v2-step-24: A2A 集成测试。
 */
@SpringBootTest
@AutoConfigureMockMvc
class A2AControllerTest {

    @Autowired MockMvc mvc;
    @Autowired A2ATaskStore store;
    @MockBean RestTemplate restTemplate; // executor 中都是 new RestTemplate(), 这里 mock 不上

    @BeforeEach
    void reset() { store.clear(); }

    @Test
    void agentCardServed() throws Exception {
        mvc.perform(get("/.well-known/agent.json"))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$.name").value("ZhiQian YunShu"))
           .andExpect(jsonPath("$.capabilities.streaming").value(true))
           .andExpect(jsonPath("$.skills.length()").value(4));
    }

    @Test
    void taskSendCreatesTask() throws Exception {
        String body = "{\"id\":\"t1\",\"message\":{\"skill\":\"sql.transpile\",\"arguments\":{\"source_sql\":\"SELECT 1\"}}}";
        mvc.perform(post("/a2a/tasks/send").contentType(MediaType.APPLICATION_JSON).content(body))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$.id").value("t1"))
           .andExpect(jsonPath("$.status.state").exists());
        assertThat(store.get("t1")).isNotNull();
    }

    @Test
    void taskGetReturns404IfMissing() throws Exception {
        mvc.perform(get("/a2a/tasks/missing"))
           .andExpect(jsonPath("$.code").value(404));
    }

    @Test
    void taskListReturnsArray() throws Exception {
        A2ATask t = new A2ATask();
        t.id = "t-list"; t.state = "submitted";
        t.createdAt = java.time.Instant.now(); t.updatedAt = t.createdAt;
        store.save(t);
        mvc.perform(get("/a2a/tasks"))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$.data").isArray())
           .andExpect(jsonPath("$.data.length()").value(org.hamcrest.Matchers.greaterThanOrEqualTo(1)));
    }
}
