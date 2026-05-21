# TTS 模块 (v2-step-26)

Spring 端代理 edge-tts CLI 生 mp3。与 RAG 端 `/tts/speak` 双轨 — 前端可选任一。

## 装

```bash
pip install edge-tts
edge-tts --version  # 验证
SPRING_PROFILES_ACTIVE=tts ./mvnw spring-boot:run
```

## 调

```bash
curl http://localhost:8080/api/tts/status
# => {"enabled":true,"engine":"edge-tts","available":true}

curl 'http://localhost:8080/api/tts/speak?text=智迁云枢为你服务' --output hello.mp3
open hello.mp3
```

## 设计动机

- 不调 OpenAI TTS (收费) / 不依 Azure SDK (重)
- edge-tts 是社区逆向 Microsoft Edge 读稿接口, 免费, 品质优于浏览器原生 SpeechSynthesis
- ProcessBuilder 外调 CLI 避免 Java side 维护 HTTPS/SSML 代码, 50 行搞定
- timeout 20s, 状态检查 3s, 防启动崩
- profile=tts 才启用, 默认 `enabled=false` -> 503, 不影响其他场景
