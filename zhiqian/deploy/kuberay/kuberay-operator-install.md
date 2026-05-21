# KubeRay Operator 安装说明

KubeRay Operator 不适合直接纳管进本 repo (它是上游项目), 推荐走 Helm 装:

```bash
helm repo add kuberay https://ray-project.github.io/kuberay-helm/
helm repo update
helm install kuberay-operator kuberay/kuberay-operator \
  --version 1.2.2 \
  -n kuberay-system \
  --create-namespace

kubectl -n kuberay-system wait --for=condition=available --timeout=300s deploy/kuberay-operator
```

如不能联外, 本地镜像:
```bash
# 1) helm pull
helm pull kuberay/kuberay-operator --version 1.2.2 -d /tmp
# 2) docker pull + retag + push 到内部 registry
# 3) helm install --set image.repository=internal-registry/kuberay/operator ...
```

上游文档: https://docs.ray.io/en/latest/cluster/kubernetes/getting-started.html
