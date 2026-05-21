# 安全策略

## 披露漏洞

请 **不要** 在公开 issue 里提交漏洞。发邮主身 (或走 GitHub Security Advisories):

- Security Advisory: https://github.com/anothersunset/zhixianyunshu/security/advisories/new
- 邮 (占位, 仓主可补): security@example.com

期望包含:
- 受影响版本 / 提交 SHA
- 复现步骤 (最小可运行)
- 冲击面: RCE / 信息泄露 / 提权 / DoS / 床佛性依赖问题
- 预期修复思路 (可选)

## 响应诺

| 严重 | 首复 24h | 修复目标 |
| --- | --- | --- |
| Critical (RCE / 身份泄) | 是 | 7 日内 |
| High (提权 / SSRF 可奥) | 是 | 14 日内 |
| Medium | 72h | 30 日内 |
| Low | 7 日 | best effort |

## 供应链保障

- **SBOM**: 每次 push main / tag v* 生 CycloneDX, artifact 90 天 (看 `.github/workflows/supply-chain.yml`)。
- **扫描**: Trivy fs scan + image scan, SARIF 上 GitHub Security tab, severity CRITICAL/HIGH。
- **签名**: Cosign keyless OIDC, 代理名为 `token.actions.githubusercontent.com`, Rekor public ledger 透明可查。
- **验证签名**:
  ```bash
  cosign verify-blob \
    --certificate sbom.cdx.json.pem \
    --signature sbom.cdx.json.sig \
    --certificate-identity-regexp '^https://github.com/anothersunset/zhixianyunshu/' \
    --certificate-oidc-issuer https://token.actions.githubusercontent.com \
    sbom.cdx.json
  ```

## 依赖报警

- Dependabot alerts 启 (Settings → Security → Dependabot)。
- npm/maven/pip 类型全覃

## 不在范围内

- 本地 demo 环境默认弱口令 (`zhiqian` / `ChangeMe!`) 仅为演示, 不能作为生产漏报。
- 仃是未启 profile=cdc / profile=tts / profile=temporal 的服务接口, 不启不影响。
- 未装依走优雅路径 (typst / edge-tts / @xenova/transformers) 是设计, 非漏。
