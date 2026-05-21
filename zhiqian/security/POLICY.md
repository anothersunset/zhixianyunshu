# 供应链安全策略 (v2-step-31)

## 全链路

```
source → Syft (SBOM) → Trivy (CVE) → Cosign keyless (sign) → SARIF (GitHub Security tab)
                        ↓                       ↓
                  SBOM artifact            Rekor public ledger
```

## SBOM

- 格式: CycloneDX JSON (GitHub Dependency Submission API 可消费)
- 范围: `zhiqian/` 全目录, 含 backend / rag / web 依赖全链
- 保留: artifact 90 天, image attestation 永久 (Rekor)

## Cosign keyless

- OIDC issuer: `token.actions.githubusercontent.com`
- Subject: `https://github.com/anothersunset/zhixianyunshu/...`
- 不需私钥/不需 KMS, 公示 Rekor 透明日志

## 验证命令

```bash
cosign verify-blob \
  --certificate sbom.cdx.json.pem \
  --signature sbom.cdx.json.sig \
  --certificate-identity-regexp '^https://github\.com/anothersunset/zhixianyunshu/.*' \
  --certificate-oidc-issuer 'https://token.actions.githubusercontent.com' \
  sbom.cdx.json

cosign verify ghcr.io/anothersunset/zhixianyunshu/backend:v2.0.0 \
  --certificate-identity-regexp '^https://github\.com/anothersunset/zhixianyunshu/.*' \
  --certificate-oidc-issuer 'https://token.actions.githubusercontent.com'

rekor-cli search --artifact sbom.cdx.json
```

## 漏洞响应 SLA

| 等级 | 响应 |
| --- | --- |
| CRITICAL | 24h 修补或 deny merge |
| HIGH     | 7 天内修补 |
| MEDIUM/LOW | 按季度 backlog |

## SLSA 定位

- 当前: **SLSA Build L2** (脚本生成 + 可逆响叒 + keyless sign)
- 路径到 L3: hermetic build (rebuildable from source pin) + provenance attestation
