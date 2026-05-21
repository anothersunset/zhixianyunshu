package com.zhiqian.agent;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

/**
 * AgentRunner 单元测试
 * 测试单节点/多节点图执行、异常处理、上下文状态传递
 */
class AgentRunnerTest {

    private AgentRunner runner;

    @BeforeEach
    void setUp() {
        runner = new AgentRunner();
    }

    // ========== 辅助方法 ==========

    /** 创建一个返回固定输出的 AgentTool */
    private AgentTool fixedOutputTool(String toolName, Map<String, Object> output) {
        return new AgentTool() {
            @Override
            public String name() { return toolName; }

            @Override
            public String description() { return "test tool: " + toolName; }

            @Override
            public Map<String, Object> run(AgentContext ctx, Map<String, Object> input) {
                return output;
            }
        };
    }

    /** 创建一个始终抛出异常的 AgentTool */
    private AgentTool failingTool(String toolName, String errorMsg) {
        return new AgentTool() {
            @Override
            public String name() { return toolName; }

            @Override
            public String description() { return "failing tool"; }

            @Override
            public Map<String, Object> run(AgentContext ctx, Map<String, Object> input) {
                throw new RuntimeException(errorMsg);
            }
        };
    }

    // ========== 单节点图执行 ==========

    @Nested
    @DisplayName("单节点图执行")
    class SingleNodeGraph {

        @Test
        @DisplayName("单节点图正常执行，返回一个 OK 状态的 step")
        void singleNodeExecutesSuccessfully() {
            Map<String, Object> output = Map.of("result", "done");
            AgentTool tool = fixedOutputTool("onlyNode", output);

            AgentGraph graph = new AgentGraph()
                .addNode("onlyNode", tool)
                .entry("onlyNode");

            AgentContext ctx = new AgentContext(1L, 100L);
            List<AgentStep> steps = new ArrayList<>();

            runner.run(graph, ctx, steps::add);

            assertEquals(1, steps.size());
            AgentStep step = steps.get(0);
            assertEquals("onlyNode", step.stage());
            assertEquals("onlyNode", step.agentName());
            assertEquals("OK", step.status());
            assertNotNull(step.elapsedMs());
            assertTrue(step.elapsedMs() >= 0);
        }

        @Test
        @DisplayName("单节点执行后输出写入上下文状态")
        void singleNodeOutputWrittenToState() {
            Map<String, Object> output = Map.of("key1", "val1", "key2", 42);
            AgentTool tool = fixedOutputTool("writer", output);

            AgentGraph graph = new AgentGraph()
                .addNode("writer", tool)
                .entry("writer");

            AgentContext ctx = new AgentContext(1L, 100L);

            runner.run(graph, ctx, step -> {});

            assertEquals("val1", ctx.state().get("key1"));
            assertEquals(42, ctx.state().get("key2"));
        }
    }

    // ========== 多节点图执行 ==========

    @Nested
    @DisplayName("多节点图执行")
    class MultiNodeGraph {

        @Test
        @DisplayName("多节点图按路由顺序依次执行")
        void multiNodeExecutesInOrder() {
            AgentTool tool1 = fixedOutputTool("step1", Map.of("a", 1));
            AgentTool tool2 = fixedOutputTool("step2", Map.of("b", 2));
            AgentTool tool3 = fixedOutputTool("step3", Map.of("c", 3));

            AgentGraph graph = new AgentGraph()
                .addNode("node1", tool1)
                .addNode("node2", tool2)
                .addNode("node3", tool3)
                .addEdge("node1", ctx -> "node2")
                .addEdge("node2", ctx -> "node3")
                .entry("node1");

            AgentContext ctx = new AgentContext(1L, 100L);
            List<AgentStep> steps = new ArrayList<>();

            runner.run(graph, ctx, steps::add);

            assertEquals(3, steps.size());
            assertEquals("node1", steps.get(0).stage());
            assertEquals("node2", steps.get(1).stage());
            assertEquals("node3", steps.get(2).stage());

            // 所有步骤状态为 OK
            steps.forEach(s -> assertEquals("OK", s.status()));
        }

        @Test
        @DisplayName("路由返回 null 时图执行终止")
        void routerReturnsNullStopsExecution() {
            AgentTool tool1 = fixedOutputTool("step1", Map.of());
            AgentTool tool2 = fixedOutputTool("step2", Map.of());

            AgentGraph graph = new AgentGraph()
                .addNode("node1", tool1)
                .addNode("node2", tool2)
                .addEdge("node1", ctx -> null) // 路由返回 null → 终止
                .entry("node1");

            AgentContext ctx = new AgentContext(1L, 100L);
            List<AgentStep> steps = new ArrayList<>();

            runner.run(graph, ctx, steps::add);

            assertEquals(1, steps.size());
            assertEquals("node1", steps.get(0).stage());
        }
    }

    // ========== 异常处理 ==========

    @Nested
    @DisplayName("节点异常处理")
    class ExceptionHandling {

        @Test
        @DisplayName("节点抛异常时状态为 FAIL")
        void exceptionNodeStatusIsFail() {
            AgentTool tool = failingTool("badNode", "something went wrong");

            AgentGraph graph = new AgentGraph()
                .addNode("badNode", tool)
                .entry("badNode");

            AgentContext ctx = new AgentContext(1L, 100L);
            List<AgentStep> steps = new ArrayList<>();

            runner.run(graph, ctx, steps::add);

            assertEquals(1, steps.size());
            AgentStep step = steps.get(0);
            assertEquals("FAIL", step.status());
            assertEquals("badNode", step.stage());
        }

        @Test
        @DisplayName("节点抛异常时 output 包含 error 信息")
        void exceptionNodeOutputContainsError() {
            AgentTool tool = failingTool("failNode", "disk full");

            AgentGraph graph = new AgentGraph()
                .addNode("failNode", tool)
                .entry("failNode");

            AgentContext ctx = new AgentContext(1L, 100L);
            List<AgentStep> steps = new ArrayList<>();

            runner.run(graph, ctx, steps::add);

            AgentStep step = steps.get(0);
            assertNotNull(step.output());
            assertEquals("disk full", step.output().get("error"));
        }

        @Test
        @DisplayName("节点抛异常后停止执行，不继续后续节点")
        void exceptionStopsSubsequentNodes() {
            AgentTool failTool = failingTool("fail", "boom");
            AgentTool afterTool = fixedOutputTool("after", Map.of());

            AgentGraph graph = new AgentGraph()
                .addNode("fail", failTool)
                .addNode("after", afterTool)
                .addEdge("fail", ctx -> "after")
                .entry("fail");

            AgentContext ctx = new AgentContext(1L, 100L);
            List<AgentStep> steps = new ArrayList<>();

            runner.run(graph, ctx, steps::add);

            assertEquals(1, steps.size());
            assertEquals("FAIL", steps.get(0).status());
            assertEquals("fail", steps.get(0).stage());
        }
    }

    // ========== 上下文状态传递 ==========

    @Nested
    @DisplayName("上下文状态传递")
    class StatePropagation {

        @Test
        @DisplayName("前一个节点的输出写入 state，后一个节点的 input 包含这些 state")
        void statePassesBetweenNodes() {
            // node1 写入 state
            AgentTool tool1 = fixedOutputTool("producer", Map.of("shared_key", "shared_value"));

            // node2 读取 input（来自 state）并输出
            AgentTool tool2 = new AgentTool() {
                @Override
                public String name() { return "consumer"; }

                @Override
                public String description() { return "consumer tool"; }

                @Override
                public Map<String, Object> run(AgentContext ctx, Map<String, Object> input) {
                    // 验证 input 包含 node1 写入的 state
                    assertEquals("shared_value", input.get("shared_key"));
                    return Map.of("consumed", true);
                }
            };

            AgentGraph graph = new AgentGraph()
                .addNode("producer", tool1)
                .addNode("consumer", tool2)
                .addEdge("producer", ctx -> "consumer")
                .entry("producer");

            AgentContext ctx = new AgentContext(1L, 100L);
            List<AgentStep> steps = new ArrayList<>();

            runner.run(graph, ctx, steps::add);

            assertEquals(2, steps.size());
            assertEquals("OK", steps.get(0).status());
            assertEquals("OK", steps.get(1).status());

            // 最终 state 包含两个节点的输出
            assertTrue(ctx.state().containsKey("shared_key"));
            assertTrue(ctx.state().containsKey("consumed"));
        }

        @Test
        @DisplayName("多个节点逐步累积 state")
        void stateAccumulatesAcrossNodes() {
            AgentTool t1 = fixedOutputTool("s1", Map.of("k1", "v1"));
            AgentTool t2 = fixedOutputTool("s2", Map.of("k2", "v2"));
            AgentTool t3 = new AgentTool() {
                @Override public String name() { return "s3"; }
                @Override public String description() { return ""; }
                @Override
                public Map<String, Object> run(AgentContext ctx, Map<String, Object> input) {
                    // 此时 input 应包含 k1, k2
                    assertEquals("v1", input.get("k1"));
                    assertEquals("v2", input.get("k2"));
                    return Map.of("k3", "v3");
                }
            };

            AgentGraph graph = new AgentGraph()
                .addNode("n1", t1)
                .addNode("n2", t2)
                .addNode("n3", t3)
                .addEdge("n1", ctx -> "n2")
                .addEdge("n2", ctx -> "n3")
                .entry("n1");

            AgentContext ctx = new AgentContext(1L, 100L);

            runner.run(graph, ctx, step -> {});

            assertEquals("v1", ctx.state().get("k1"));
            assertEquals("v2", ctx.state().get("k2"));
            assertEquals("v3", ctx.state().get("k3"));
        }

        @Test
        @DisplayName("AgentContext 的 taskId 和 projectId 保持不变")
        void contextIdsPreserved() {
            AgentTool tool = new AgentTool() {
                @Override public String name() { return "check"; }
                @Override public String description() { return ""; }
                @Override
                public Map<String, Object> run(AgentContext ctx, Map<String, Object> input) {
                    assertEquals(42L, ctx.taskId());
                    assertEquals(99L, ctx.projectId());
                    return Map.of();
                }
            };

            AgentGraph graph = new AgentGraph()
                .addNode("check", tool)
                .entry("check");

            AgentContext ctx = new AgentContext(42L, 99L);

            runner.run(graph, ctx, step -> {});

            assertEquals(42L, ctx.taskId());
            assertEquals(99L, ctx.projectId());
        }
    }

    // ========== AgentStep record 字段验证 ==========

    @Nested
    @DisplayName("AgentStep 字段验证")
    class AgentStepFields {

        @Test
        @DisplayName("AgentStep 的 input 是上下文状态的快照")
        void stepInputIsStateSnapshot() {
            // 先预设一些 state
            AgentTool preset = new AgentTool() {
                @Override public String name() { return "preset"; }
                @Override public String description() { return ""; }
                @Override
                public Map<String, Object> run(AgentContext ctx, Map<String, Object> input) {
                    ctx.state().put("preexisting", "data");
                    return Map.of("newKey", "newVal");
                }
            };

            AgentTool reader = new AgentTool() {
                @Override public String name() { return "reader"; }
                @Override public String description() { return ""; }
                @Override
                public Map<String, Object> run(AgentContext ctx, Map<String, Object> input) {
                    return Map.of();
                }
            };

            AgentGraph graph = new AgentGraph()
                .addNode("preset", preset)
                .addNode("reader", reader)
                .addEdge("preset", ctx -> "reader")
                .entry("preset");

            AgentContext ctx = new AgentContext(1L, 100L);
            List<AgentStep> steps = new ArrayList<>();

            runner.run(graph, ctx, steps::add);

            // 第二个 step 的 input 应该包含 preset 的输出
            AgentStep step2 = steps.get(1);
            assertTrue(step2.input().containsKey("preexisting"));
            assertTrue(step2.input().containsKey("newKey"));
        }
    }
}
