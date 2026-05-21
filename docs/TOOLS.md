# CLI 工具版本矩阵

完整 demo 路径需要的 CLI 工具。标 **必** 是启不了, 标 **选** 是不装也能走 (优雅降级)。

| 工具 | 要求版本 | 是否必 | 装 | 用于 |
| --- | --- | --- | --- | --- |
| `git` | ≥2.30 | 必 | apt/brew/yum | 全仓库 |
| `docker` + `compose` v2 | ≢4.0 / ≥2.0 | 必 | [docker.com](https://docs.docker.com/get-docker/) | datasets / cdc / argocd |
| `java` | 21 LTS | 必 | [sdkman.io](https://sdkman.io) `sdk install java 21.0.4-tem` | backend |
| `maven` 或 wrapper | ≥3.9 | 必 | `./mvnw` 自包 | backend |
| `python3` | ≥3.11 | 必 | apt/brew/pyenv | rag |
| `pip` 或 `uv` | latest | 必 | 随 python | rag 依 |
| `node` | ≥20 LTS | 必 | nvm | web |
| `pnpm` | ≥9 | 必 | `corepack enable && corepack prepare pnpm@latest --activate` | web |
| `curl` | 任 | 必 | 内置 | healthcheck · datasets |
| `mysql` client | ≥5.7 | 必 | apt/brew | sakila/chinook seed |
| `typst` | ≥0.11 | 选 | `brew install typst` 或 `cargo install typst-cli` | #27 PDF 报告 |
| `edge-tts` | ≥6.1 | 选 | `pip install edge-tts` | #26 读稿 |
| `syft` | ≥1.x | 选 | `brew install syft` | #31 SBOM 本地 |
| `trivy` | ≥0.50 | 选 | `brew install trivy` | #31 扫描本地 |
| `cosign` | ≥v2.4 | 选 | `brew install cosign` | #31 签名本地 |
| `kubectl` | ≥1.28 | 选 | 随 kubectl | k8s 部署 |
| `kustomize` | ≥5.0 | 选 | 随 kubectl 内置 | k8s overlays |
| `argocd` cli | ≥2.10 | 选 | [argo-cd releases](https://github.com/argoproj/argo-cd/releases) | #19 GitOps |
| `helm` | ≦3.x | 选 | 不推荐 (项目已 pivot Kustomize) | 仅装 ArgoCD 本身 |
| `temporal` cli | ≥1.x | 选 | `brew install temporal` | #14 本地 worker 调 |
| `pyflakes` | 任 | 选 | `pip install pyflakes` | smoke-test rag lint |

## 一键安装 (macOS)

```bash
brew install git docker docker-compose openjdk@21 maven node pnpm python@3.12 curl mysql-client typst
pip install edge-tts pyflakes
brew install syft trivy cosign     # 供应链 (可缓)
brew install kubectl helm argocd   # K8s 部署 (可缓)
```

## 一键安装 (Ubuntu 22.04+)

```bash
sudo apt update && sudo apt install -y git docker.io docker-compose-plugin openjdk-21-jdk maven nodejs npm python3 python3-pip curl mysql-client
sudo npm install -g pnpm
pip install edge-tts pyflakes

# typst
curl -fsSL https://typst.community/typst-install/install.sh | sh

# 供应链 (可缓)
curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh -s -- -b /usr/local/bin
curl -sSfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin
go install github.com/sigstore/cosign/v2/cmd/cosign@latest
```

## 验证环境

```bash
bash scripts/smoke-test.sh     # 接着快检
```

## 分层启动

| 场景 | 需要 | 可跳 |
| --- | --- | --- |
| 仅看 README + UPGRADE_PLAN | git | 其他全跳 |
| smoke-test | java + python + node + pnpm | docker/mysql/typst/edge-tts |
| local demo (不 CDC) | + docker + mysql client | k8s/typst/edge-tts |
| local demo (全) | + typst + edge-tts | k8s |
| K8s prod | + kubectl + kustomize + argocd | local docker |
| 供应链 CI 本地验 | + syft + trivy + cosign | k8s |
