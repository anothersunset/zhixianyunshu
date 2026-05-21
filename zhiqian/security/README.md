# Security 目录 (v2-step-31)

- `POLICY.md` — 供应链安全策略, SLSA 定位, 验证命令
- `sbom-attestation-template.json` — SLSA provenance 模板
- `workflows-template/supply-chain.yml` — 手动拷贝到 `.github/workflows/`

## 快速打开供应链 CI

```bash
mkdir -p .github/workflows
cp zhiqian/security/workflows-template/supply-chain.yml .github/workflows/
git add .github/workflows/supply-chain.yml
git commit -m 'ci: enable supply-chain CI'
git push
```

## 本地生 SBOM + 扫描

```bash
brew install syft trivy cosign
syft ./zhiqian -o cyclonedx-json > sbom.cdx.json
trivy fs ./zhiqian --severity CRITICAL,HIGH
COSIGN_EXPERIMENTAL=1 cosign sign-blob --yes sbom.cdx.json
```
