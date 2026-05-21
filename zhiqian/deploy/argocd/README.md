# ZhiQian YunShu ArgoCD GitOps

> v2-step-19 交付。在 #18 Kustomize 上套 ArgoCD declarative GitOps, 实现 git push → 自动同步集群。

## 为什么走 GitOps

- **声明式**: git 是容性 source of truth, 容器手工 patch 不会偏离
- **可审计**: 每次部署可追溯到 git commit
- **可回滚**: git revert + auto sync 即可回滚
- **多环境**: AppProject + Application 隔离 dev/staging/prod RBAC + namespace
- **drift detection**: 集群状态与 git 偏离时 ArgoCD UI 高亮

## 目录内容

```
argocd/
  argocd-namespace.yaml      # argocd ns
  project.yaml               # AppProject zhiqian (RBAC + source/dest 限定)
  application-dev.yaml       # Application 指 overlays/dev, automated sync
  application-prod.yaml      # Application 指 overlays/prod, manual sync + selfHeal
  app-of-apps.yaml           # 根应用 (可选)
  bootstrap.sh               # 一键装 ArgoCD + 注册上面 所有资源
```

## 一键启动

```bash
# 1) 运行 bootstrap 脚本 (同时装 ArgoCD + 注册项目)
bash zhiqian/deploy/argocd/bootstrap.sh

# 2) 访问 ArgoCD UI
kubectl -n argocd port-forward svc/argocd-server 8443:443
# → https://localhost:8443  (admin / 脚本输出的初始密码)

# 3) 看同步状态
kubectl -n argocd get applications
kubectl -n argocd describe app zhiqian-dev
```

## 常用操作

### 手动触发 sync (prod)
```bash
argocd app sync zhiqian-prod
```

### 看论象开关
```bash
argocd app diff zhiqian-prod                 # 看 git vs cluster diff
argocd app history zhiqian-prod              # sync 历史
argocd app rollback zhiqian-prod <revision>  # 回滚到某个 revision
```

### 更新 image tag
推荐 ArgoCD Image Updater, 或手工修 `kustomization.yaml` 的 `images.newTag` 提交 git。

## 生产加固清单

- [ ] argocd-server 加 Ingress + TLS
- [ ] 启用 SSO (OIDC / SAML / LDAP)
- [ ] 禁用 admin 账号, 走组权限
- [ ] 装 ArgoCD Notifications -> Slack/企业微信
- [ ] secret 走 External Secrets Operator / Sealed Secrets / Vault
- [ ] 装 Argo Image Updater 自动 bump container tag
- [ ] prod 开 manual sync, dev/staging 开 automated
- [ ] 配 sync windows 控制部署时间窗

## App-of-apps 模式 (可选)

仅需 apply 根应用, ArgoCD 会自动 sync project + 2 个子应用:
```bash
kubectl apply -f zhiqian/deploy/argocd/app-of-apps.yaml
```

## 故障排查

### Application stuck OutOfSync
```bash
argocd app sync zhiqian-dev --force --replace
kubectl -n argocd logs deploy/argocd-application-controller -f
```

### 密码丢失 / 重置 admin
```bash
kubectl -n argocd patch secret argocd-secret -p '{"stringData":{"admin.password":"","admin.passwordMtime":""}}'
kubectl -n argocd rollout restart deploy argocd-server
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d
```
