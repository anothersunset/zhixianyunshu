# 端侧推理 (v2-step-28)

完全走浏览器 —— 适合演示 / 火车 / 离线 场景。

## 依赖

```bash
cd zhiqian/web
pnpm add @xenova/transformers
```

package.json 已在 README 里列出, 该依赖可选: 不装时 useLocalLlm 返 error 但不崩。

## 技术选型

- **transformers.js v3**: Xenova 出, ONNX Runtime Web 底层
- **Phi-3.5-mini-instruct-onnx-web**: Microsoft 3.8B param, q4 量化后 ~600MB
- **WebGPU 优先**: Chrome 113+, 推理速度 ×10 于 WASM
- **WASM 降级**: 所有现代浏览器均可跑, ~5 tok/s

## 为什么

- **隐私**: 数据不出浏览器
- **零推理成本**: 设计发布后不吃 GPU 资源
- **论文加分**: Edge AI / 端侧智能 是 2024-2026 热点
