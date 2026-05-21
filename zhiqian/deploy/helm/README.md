# Helm Chart (deprecated)

> **v2-step-18 决策**: Helm 目录已 deprecated。文件推送代理不能保留 Helm Go-template `{` `{` `}` `}` 语法。部署路径请走 `zhiqian/deploy/kustomize/`。

## 为什么走 Kustomize

- ArgoCD 原生消费 Kustomize (#19 下一步)
- 纯 YAML, 无需渲染, kubectl 1.14+ 内置
- overlay 机制多环境复用 base
- secretGenerator/configMapGenerator 代替 Helm secret/configmap template

## 补充

如他后需要 Helm chart, 可手工 / 用 [kompose](https://kompose.io/) 转换 / 用 [chartmuseum-helmify](https://github.com/arttor/helmify) 从 Kustomize manifests 生成。

Chart.yaml / values.yaml 保留作为参考架构设计文档。
