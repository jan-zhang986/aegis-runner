# Aegis Runner - K8s 部署指南

## 🚀 快速部署（3 步完成）

### 第 1 步：准备 Kafka Topics

```bash
# 连接到 Kafka Pod
kubectl exec -it <kafka-pod-name> -n <namespace> -- bash

# 创建 3 个 Topics
kafka-topics.sh --create --topic task-urgent --bootstrap-server localhost:9092 --partitions 3 --replication-factor 2
kafka-topics.sh --create --topic task-high --bootstrap-server localhost:9092 --partitions 3 --replication-factor 2
kafka-topics.sh --create --topic task-normal --bootstrap-server localhost:9092 --partitions 3 --replication-factor 2

# 验证
kafka-topics.sh --list --bootstrap-server localhost:9092
```

### 第 2 步：修改配置文件

#### 2.1 修改 `deployments/k8s/secrets.yaml`

```bash
# 生成密码的 base64 编码
echo -n "你的数据库密码" | base64
echo -n "你的Redis密码" | base64  # 如果有的话

# 编辑文件，替换密码
vim deployments/k8s/secrets.yaml
```

#### 2.2 修改 `deployments/k8s/configmap.yaml` 和 Deployment 文件

根据你的实际环境修改：
- Kafka 地址
- Redis 地址
- MySQL 地址

### 第 3 步：部署到 K8s

#### 方式 A：使用云效 CI/CD（推荐）

1. 在云效配置 CI/CD 流水线
2. 添加构建步骤：
   ```bash
   # 构建 Master 镜像
   docker build -t registry.cn-hangzhou.aliyuncs.com/spotter/runner:${VERSION} -f Dockerfile .
   docker push registry.cn-hangzhou.aliyuncs.com/spotter/runner:${VERSION}
   
   # 构建 Worker 镜像
   docker build -t registry.cn-hangzhou.aliyuncs.com/spotter/runner-worker:${VERSION} -f Dockerfile.worker .
   docker push registry.cn-hangzhou.aliyuncs.com/spotter/runner-worker:${VERSION}
   ```

3. 添加部署步骤：
   ```bash
   # 应用配置
   kubectl apply -f deployments/k8s/configmap.yaml -n default
   kubectl apply -f deployments/k8s/secrets.yaml -n default
   
   # 部署 Master 和 Worker
   kubectl apply -f deployments/k8s/master-deployment.yaml -n default
   kubectl apply -f deployments/k8s/worker-deployment.yaml -n default
   kubectl apply -f deployments/k8s/master-service.yaml -n default
   kubectl apply -f deployments/k8s/hpa.yaml -n default
   
   # 更新镜像
   kubectl set image deployment/aegis-runner-master master=registry.cn-hangzhou.aliyuncs.com/spotter/runner:${VERSION} -n default
   kubectl set image deployment/aegis-runner-worker worker=registry.cn-hangzhou.aliyuncs.com/spotter/runner-worker:${VERSION} -n default
   ```

#### 方式 B：手动部署

```bash
# 1. 给脚本添加执行权限
chmod +x deployments/scripts/deploy.sh

# 2. 执行部署（脚本会自动完成所有步骤）
./deployments/scripts/deploy.sh prod
```

---

## 📊 验证部署

```bash
# 查看 Pods 状态（应该都是 Running）
kubectl get pods -l app=aegis-runner -n default

# 查看日志
kubectl logs -f deployment/aegis-runner-master -n default
kubectl logs -f deployment/aegis-runner-worker -n default

# 测试 API
curl http://<service-ip>:8100/health
```

---

## 🔧 日常运维

### 扩容 Worker

```bash
# 方式 1：使用脚本
./deployments/scripts/scale-workers.sh 10

# 方式 2：使用 kubectl
kubectl scale deployment aegis-runner-worker --replicas=10 -n default
```

### 查看状态

```bash
# 查看 Pods
kubectl get pods -l app=aegis-runner -n default

# 查看资源使用
kubectl top pods -l app=aegis-runner -n default

# 查看自动扩缩容状态
kubectl get hpa -n default
```

### 更新部署

```bash
# 更新镜像版本
kubectl set image deployment/aegis-runner-master master=registry.cn-hangzhou.aliyuncs.com/spotter/runner:v2.0.0 -n default
kubectl set image deployment/aegis-runner-worker worker=registry.cn-hangzhou.aliyuncs.com/spotter/runner-worker:v2.0.0 -n default

# 或者重新执行部署脚本
./deployments/scripts/deploy.sh prod
```

### 回滚

```bash
# 回滚到上一个版本
kubectl rollout undo deployment/aegis-runner-master -n default
kubectl rollout undo deployment/aegis-runner-worker -n default
```

---

## 🐛 常见问题

### 1. Pod 无法启动

```bash
# 查看详情
kubectl describe pod <pod-name> -n default

# 查看日志
kubectl logs <pod-name> -n default
```

**常见原因**：
- 镜像拉取失败 → 检查镜像地址和权限
- 配置错误 → 检查 ConfigMap 和 Secrets
- Kafka/Redis/MySQL 连接失败 → 检查网络和配置

### 2. Worker 无法消费任务

```bash
# 检查 Kafka Topics
kubectl exec -it <kafka-pod> -- kafka-topics.sh --list --bootstrap-server localhost:9092

# 检查 Worker 日志
kubectl logs -f deployment/aegis-runner-worker -n default
```

### 3. 内存不足

```bash
# 增加内存限制
kubectl edit deployment aegis-runner-worker -n default
# 修改 resources.limits.memory 为更大的值（如 4Gi）
```

---

## 📁 重要文件说明

| 文件 | 用途 |
|------|------|
| `Dockerfile` | Master 镜像（已存在） |
| `Dockerfile.worker` | Worker 镜像 |
| `deployments/k8s/master-deployment.yaml` | Master 部署配置 |
| `deployments/k8s/worker-deployment.yaml` | Worker 部署配置 |
| `deployments/k8s/master-service.yaml` | Service 配置 |
| `deployments/k8s/configmap.yaml` | 应用配置 |
| `deployments/k8s/secrets.yaml` | 密钥配置 |
| `deployments/k8s/hpa.yaml` | 自动扩缩容 |
| `deployments/scripts/deploy.sh` | 一键部署脚本 |
| `deployments/scripts/scale-workers.sh` | 扩缩容脚本 |

---

## 📞 需要帮助？

- 详细文档：查看 `MASTER_WORKER_MIGRATION.md`
- 联系人：Fred.fan (fred.fan@spotterio.com)

---

**就这么简单！3 步完成部署，其他文件都是辅助文档，可以按需查看。**
