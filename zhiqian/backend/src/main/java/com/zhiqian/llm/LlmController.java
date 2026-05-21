package com.zhiqian.llm;

import com.zhiqian.common.Result;
import org.springframework.web.bind.annotation.*;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * /api/llm/* 路径。提供三个端点：
 * <ul>
 *   <li>GET  /api/llm/health — 快速检查当前 LLM provider 与是否为真实接入</li>
 *   <li>POST /api/llm/chat   — 调试用接口，直接传递 prompt 看返回</li>
 *   <li>POST /api/llm/reason — 调用 reasoner 模型（R1 类）</li>
 * </ul>
 * 走 JWT 鉴权，需先 POST /api/auth/login 拿 token。
 * <p>v2-step-03 修复：Result 静态工厂方法名为 ok，不是 success。</p>
 */
@RestController
@RequestMapping("/api/llm")
public class LlmController {

    private final LlmClient llm;

    public LlmController(LlmClient llm) { this.llm = llm; }

    @GetMapping("/health")
    public Result<Map<String, Object>> health() {
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("provider", llm.providerName());
        data.put("real", llm.isReal());
        return Result.ok(data);
    }

    @PostMapping("/chat")
    public Result<Map<String, Object>> chat(@RequestBody Map<String, String> body) {
        String prompt = body.getOrDefault("prompt", "");
        long t0 = System.currentTimeMillis();
        String reply = llm.chat(prompt);
        long elapsed = System.currentTimeMillis() - t0;
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("provider", llm.providerName());
        data.put("real", llm.isReal());
        data.put("elapsedMs", elapsed);
        data.put("reply", reply);
        return Result.ok(data);
    }

    @PostMapping("/reason")
    public Result<Map<String, Object>> reason(@RequestBody Map<String, String> body) {
        String prompt = body.getOrDefault("prompt", "");
        long t0 = System.currentTimeMillis();
        String reply = llm.reason(prompt);
        long elapsed = System.currentTimeMillis() - t0;
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("provider", llm.providerName());
        data.put("real", llm.isReal());
        data.put("elapsedMs", elapsed);
        data.put("reply", reply);
        return Result.ok(data);
    }
}
