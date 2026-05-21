# KubeRay + vLLM 本地 GPU 推理 (可选)

> v2-step-20。让 ZhiQian 本地跑开源 LLM 避开 DeepSeek API 可用性/成本/数据不出站问题。vLLM 业界部署 SOTA (PagedAttention + ContinuousBatching), 同 GPU 吞吐是 HuggingFace transformers 的 5-24×。KubeRay 是官方 K8s Ray operator, RayService 提供热升级 + 多副本路由。

## 三选一主选型

| 选型 | 适用场景 | GPU 需求 | 优点 | 缺点 |
| --- | --- | --- | --- | --- |
| **A. DeepSeek SaaS** (默认) | 生产快起 | 0 | 0 运维, 最强效果 | 数据出站, 需 API key |
| **B. 独立 vLLM Deployment** | 企业私化 + 单 GPU | 1×A10/L4/3090+ (24GB) | 部署简单, OpenAI compat | 不能 HPA 跨 GPU |
| **C. KubeRay RayService** | 高可用 + 多 GPU + 70B+ | 2上, A100/H100 佳 | 热升级, autoscaler, 跨节点 | 运维复杂, Ray learning curve |

选定各点 backend application.yml 配:
```yaml
app:
  llm:
    provider: deepseek    # A. SaaS
    api-key: "${DEEPSEEK_API_KEY}"
    base-url: https://api.deepseek.com
```
```yaml
app:
  llm:
    provider: deepseek    # B. 本地 vLLM (vLLM 兼容 OpenAI API)
    api-key: "EMPTY"      # vLLM 不检 key
    base-url: http://vllm.zhiqian.svc.cluster.local:8000/v1
    chat-model: Qwen/Qwen2.5-7B-Instruct
```
```yaml
app:
  llm:
    provider: deepseek    # C. RayService (同上, 换 svc)
    api-key: "EMPTY"
    base-url: http://rayservice-vllm-serve-svc.zhiqian.svc.cluster.local:8000/v1
    chat-model: Qwen/Qwen2.5-7B-Instruct
```

## 一键启动 (选型 B 独立 vLLM)

```bash
# 1) 预检查 GPU
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.allocatable.nvidia\.com/gpu}{"\n"}{end}'
# 需看到 ≥1块 GPU

# 2) 装 NVIDIA device plugin (如未装)
kubectl create -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.15.0/nvidia-device-plugin.yml

# 3) 部署 vLLM Deployment
kubectl apply -f zhiqian/deploy/kuberay/vllm-deployment.yaml
kubectl -n zhiqian wait --for=condition=available --timeout=600s deploy/vllm
# 首次拉模型 ≈20 min (7B 约15GB)

# 4) 烟测
kubectl -n zhiqian port-forward svc/vllm 8000:8000
curl http://localhost:8000/v1/models | jq
curl -X POST http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"Qwen/Qwen2.5-7B-Instruct","messages":[{"role":"user","content":"你是谁"}]}'

# 5) backend 切换 profile
# zhiqian/deploy/kustomize/overlays/dev/kustomization.yaml 增:
#   patches: [{ target: { kind: Deployment, name: zhiqian-backend }, patch: |-
#     - op: add
#       path: /spec/template/spec/containers/0/env/-
#       value: { name: SPRING_PROFILES_ACTIVE, value: "vllm" } }]
```

## 选型 C: RayService (高可用 + autoscaler)

```bash
# 1) 装 KubeRay Operator
helm repo add kuberay https://ray-project.github.io/kuberay-helm/
helm repo update
helm install kuberay-operator kuberay/kuberay-operator --version 1.2.2 -n kuberay-system --create-namespace

# 2) 部署 RayService
kubectl apply -f zhiqian/deploy/kuberay/rayservice-vllm.yaml
kubectl -n zhiqian get rayservice
kubectl -n zhiqian get pods -l ray.io/cluster=rayservice-vllm

# 3) 热升级模型 (仅改 yaml 重 apply, Ray 不中断服务)
# 改 rayservice-vllm.yaml 中 serveConfigV2 的 model_id 为 Qwen/Qwen2.5-14B-Instruct
kubectl apply -f zhiqian/deploy/kuberay/rayservice-vllm.yaml
```

## 性能估算 (Qwen2.5-7B-Instruct fp16)

| GPU | 吞吐 (tok/s) | 并发 | 显存 |
| --- | --- | --- | --- |
| RTX 3090 24GB | ~2500 | 32 | 15GB |
| A10 24GB | ~3000 | 64 | 15GB |
| L4 24GB | ~3200 | 64 | 15GB |
| A100 40GB | ~6500 | 128 | 15GB |
| H100 80GB | ~12000 | 256 | 15GB |

INT4 量化后显存 ≈4GB, 可跑在 RTX 4060 Ti 16GB 上 (使用 awq=true)。

## 生产加固清单

- [ ] vllm-deployment 加 livenessProbe (/health)
- [ ] 多副本 + Service load balancing
- [ ] PVC 缓存 HuggingFace 模型避免重复拉
- [ ] 启 vllm metrics (Prometheus scrape /metrics)
- [ ] 改用 GPTQ/AWQ 量化压低显存
- [ ] backend LlmClient 加 timeout/retry (vLLM 上下文超 32K 会慍)
- [ ] HF mirror: env HF_ENDPOINT=https://hf-mirror.com 加速国内拉模型
