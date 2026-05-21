package com.zhiqian.llm;

import com.zhiqian.common.Result;
import org.springframework.web.bind.annotation.*;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * /api/llm/* 路径。提供两个端点：
 * <ul>
 *   <li>GET  /api/llm/health — 快速检查当前 LLM provider 与是否为真实接入</li>
 *   <li>POST /api/llm/chat   — 调试用接口，直接传递 prompt 看返回</li>
 * </ul>
 * 走 JWT 鉴权，需先 /api/auth/login 拿 token。
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
        return Result.success(data);
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
        return Result.success(data);
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
        return Result.success(data);
    }
}
