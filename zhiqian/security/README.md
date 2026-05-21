# Security 目录 (v2-step-31, polish)

- `POLICY.md` — 供应链安全策略, SLSA 定位, 验证命令
- `sbom-attestation-template.json` — SLSA provenance 模板
- `workflows-template/supply-chain.yml` — GitHub Actions workflow 模板 (含占位符)

## 为什么走 template + 一键脚本?

上游集成 push 限制 `.github/workflows/*` 写入 (403)。同时平台 URL 压缩机制
会吞掉 Vue/GitHub Actions 里的 `$ … ` 二重大括号。为避免两者, 模板中的
表达式 胷写为 `$ github.repository_owner ` (单 `$` + 上下空格包裹 ref)。
启用时用 `scripts/install-supply-chain-workflow.sh` sed 转换后写入 `.github/workflows/`。

## 一键启动供应链 CI

```bash
bash scripts/install-supply-chain-workflow.sh
git add .github/workflows/supply-chain.yml
git commit -m 'ci: enable supply-chain workflow'
git push
```

验证: 推后去 GitHub Actions tab 看 workflow 是否 enable 成功, push commit 调起。

## 什么是占位符?

模板里你会看到这样的行 (注意 `$` 单 不是双, 且上下有空格):

```yaml
username: $ github.repository_owner 
password: $ secrets.GITHUB_TOKEN 
```

都会被脚本转为:

```yaml
username: $ github.repository_owner 
password: $ secrets.GITHUB_TOKEN 
```

## 本地生 SBOM + 扫描

```bash
brew install syft trivy cosign
syft ./zhiqian -o cyclonedx-json > sbom.cdx.json
trivy fs ./zhiqian --severity CRITICAL,HIGH
COSIGN_EXPERIMENTAL=1 cosign sign-blob --yes sbom.cdx.json
```

## 验证别人的签名 (消费者场景)

```bash
cosign verify-blob \
  --certificate sbom.cdx.json.pem \
  --signature sbom.cdx.json.sig \
  --certificate-identity-regexp '^https://github.com/anothersunset/zhixianyunshu/' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  sbom.cdx.json
```
