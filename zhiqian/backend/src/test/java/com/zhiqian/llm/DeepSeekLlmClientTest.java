package com.zhiqian.llm;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.atomic.AtomicInteger;

import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withStatus;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * DeepSeekLlmClient 重试/限流/退避行为测试（:86-126 一带）。
 *
 * <p>用 com.sun.net.httpserver.HttpServer 在本地回环口模拟 OpenAI 兼容端点的
 * 状态码序列，通过包私有构造器注入 RestClient、包私有字段缩短退避，验证：
 * 瞬时 5xx 重试后成功、429 不重试立即失败、重试耗尽后的最终失败、以及
 * 200 但空 choices 的契约违规路径。</p>
 */
class DeepSeekLlmClientTest {

    private static final String OK_BODY = """
        {"id":"chatcmpl-test","choices":[{"index":0,
         "message":{"role":"assistant","content":"HELLO-ZHIQIAN"},"finish_reason":"stop"}],
         "usage":{"prompt_tokens":5,"completion_tokens":3,"total_tokens":8}}
        """;
    private static final String ERR_500_BODY = """
        {"error":{"message":"upstream boom","type":"server_error"}}
        """;
    private static final String ERR_429_BODY = """
        {"error":{"message":"rate limited","type":"rate_limit_exceeded"}}
        """;

    private HttpServer server;
    private final List<Integer> seenStatusesServed = new CopyOnWriteArrayList<>();
    private final AtomicInteger cursor = new AtomicInteger();
    private volatile List<int[]> script = List.of();  // 每项 {status, 0=err500体,1=err429体,2=ok体}

    private LlmProperties props;

    @BeforeEach
    void start() throws IOException {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/chat/completions", ex -> {
            ex.getRequestBody().readAllBytes(); // 消费请求体
            int[] step = script.get(Math.min(cursor.getAndIncrement(), script.size() - 1));
            seenStatusesServed.add(step[0]);
            switch (step[1]) {
                case 1 -> respond(ex, step[0], ERR_500_BODY);
                case 2 -> respond(ex, step[0], ERR_429_BODY);
                default -> respond(ex, step[0], OK_BODY);
            }
        });
        server.start();

        props = new LlmProperties();
        props.setBaseUrl("http://127.0.0.1:" + server.getAddress().getPort());
        props.setApiKey("test-key");
        props.setChatModel("test-chat");
        props.setTimeoutSeconds(5);
    }

    @AfterEach
    void stop() {
        if (server != null) server.stop(0);
    }

    private DeepSeekLlmClient client() {
        DeepSeekLlmClient c = new DeepSeekLlmClient(props, null, buildRestClient(props.getBaseUrl()));
        c.retryBackoffBaseMs = 30; // 测试加速：退避 30ms/60ms
        return c;
    }

    private static RestClient buildRestClient(String baseUrl) {
        SimpleClientHttpRequestFactory rf = new SimpleClientHttpRequestFactory();
        rf.setConnectTimeout(2000);
        rf.setReadTimeout(5000);
        return RestClient.builder().baseUrl(baseUrl).requestFactory(rf).build();
    }

    @Test
    void chatSucceedsAfterRetryingTransient500() {
        // 500（OpenAI 风格 JSON 错误体）→ 退避重试 → 200
        script = List.of(new int[]{500, 1}, new int[]{200, 0});

        long startedAt = System.currentTimeMillis();
        String content = client().chat("translate this");

        assertThat(content).isEqualTo("HELLO-ZHIQIAN");
        assertThat(seenStatusesServed).containsExactly(500, 200); // 恰好重试了一次
        assertThat(System.currentTimeMillis() - startedAt).isGreaterThanOrEqualTo(30); // 发生了退避等待
    }

    @Test
    void chatDoesNotRetryOn429AndFailsFast() {
        // 429 限流：不重试（脚本里的 200 不应被消费）
        script = List.of(new int[]{429, 2}, new int[]{200, 0});

        assertThatThrownBy(() -> client().chat("translate this"))
            .isInstanceOf(IllegalStateException.class)
            .hasMessageContaining("LLM 调用失败:")
            .hasMessageContaining("429") // 状态码回到上层消息，可识别限流
            .hasCauseInstanceOf(org.springframework.web.client.RestClientException.class);
        assertThat(seenStatusesServed).containsExactly(429); // 只打了 1 次
    }

    @Test
    void chatFailsAfterRetriesExhausted() {
        script = List.of(new int[]{500, 1});

        long startedAt = System.currentTimeMillis();
        assertThatThrownBy(() -> client().chat("translate this"))
            .isInstanceOf(IllegalStateException.class)
            .hasMessageContaining("LLM 调用失败:")
            .hasMessageContaining("500");

        assertThat(seenStatusesServed).containsExactly(500, 500, 500); // 1 次初始 + 2 次重试
        // 指数退避：30ms + 60ms 至少都等待了
        assertThat(System.currentTimeMillis() - startedAt).isGreaterThanOrEqualTo(90);
    }

    @Test
    void chatFailsWhen200ResponseHasNoChoices() {
        String emptyChoices = "{\"id\":\"x\",\"choices\":[],\"usage\":null}";
        script = List.of(new int[]{200, 9});
        server.removeContext("/chat/completions");
        server.createContext("/chat/completions", ex -> {
            ex.getRequestBody().readAllBytes();
            seenStatusesServed.add(200);
            respond(ex, 200, emptyChoices);
        });

        assertThatThrownBy(() -> client().chat("translate this"))
            .isInstanceOf(IllegalStateException.class)
            .hasMessageContaining("LLM 返回为空");
        assertThat(seenStatusesServed).containsExactly(200);
    }

    @Test
    void chatDoesNotRetryWhen429BodyIsReadableJson() {
        // DeepSeek 真实形态：429 + 可读的 OpenAI 风格 JSON 错误体（MockRestServiceServer
        // 不经过传输层，错误体总是可读——覆盖 exchange() 读到错误体的分支）。
        RestClient.Builder builder = RestClient.builder();
        MockRestServiceServer mockServer = MockRestServiceServer.bindTo(builder).build();
        mockServer.expect(requestTo(org.hamcrest.Matchers.endsWith("/chat/completions")))
            .andExpect(method(org.springframework.http.HttpMethod.POST))
            .andRespond(withStatus(org.springframework.http.HttpStatus.TOO_MANY_REQUESTS)
                .contentType(org.springframework.http.MediaType.APPLICATION_JSON)
                .body(ERR_429_BODY));

        DeepSeekLlmClient c = new DeepSeekLlmClient(props, null,
            builder.baseUrl(props.getBaseUrl()).build());
        c.retryBackoffBaseMs = 30;

        assertThatThrownBy(() -> c.chat("translate this"))
            .isInstanceOf(IllegalStateException.class)
            .hasMessageContaining("LLM 调用失败:")
            .hasMessageContaining("LLM HTTP 429")
            .hasMessageContaining("rate limited"); // 错误体片段被带回上层消息
        mockServer.verify(); // 恰好 1 次请求：429 不重试
    }

    private static void respond(HttpExchange ex, int status, String body) throws IOException {
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        ex.getResponseHeaders().set("Content-Type", "application/json");
        ex.sendResponseHeaders(status, bytes.length);
        try (OutputStream os = ex.getResponseBody()) {
            os.write(bytes);
        }
    }
}
