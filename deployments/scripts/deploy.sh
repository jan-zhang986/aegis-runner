#!/bin/bash

# Aegis Runner 部署脚本
# 用于手动部署到 K8s 集群

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置
DOCKER_REGISTRY="registry.cn-hangzhou.aliyuncs.com"
DOCKER_NAMESPACE="spotter"
MASTER_IMAGE="runner"
WORKER_IMAGE="runner-worker"
K8S_NAMESPACE="default"

# 获取版本号（使用 git commit hash）
VERSION=$(git rev-parse --short HEAD)

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Aegis Runner 部署脚本${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 检查参数
if [ "$1" == "" ]; then
    echo -e "${RED}错误: 请指定部署环境 (test/prod)${NC}"
    echo "用法: ./deploy.sh [test|prod]"
    exit 1
fi

ENVIRONMENT=$1

echo -e "${YELLOW}部署环境: $ENVIRONMENT${NC}"
echo -e "${YELLOW}版本号: $VERSION${NC}"
echo ""

# 1. 构建 Docker 镜像
echo -e "${GREEN}[1/5] 构建 Docker 镜像...${NC}"

echo "构建 Master 镜像..."
docker build -t $DOCKER_REGISTRY/$DOCKER_NAMESPACE/$MASTER_IMAGE:$VERSION -f deployments/docker/Dockerfile.master .
docker tag $DOCKER_REGISTRY/$DOCKER_NAMESPACE/$MASTER_IMAGE:$VERSION $DOCKER_REGISTRY/$DOCKER_NAMESPACE/$MASTER_IMAGE:latest

echo "构建 Worker 镜像..."
docker build -t $DOCKER_REGISTRY/$DOCKER_NAMESPACE/$WORKER_IMAGE:$VERSION -f deployments/docker/Dockerfile.worker .
docker tag $DOCKER_REGISTRY/$DOCKER_NAMESPACE/$WORKER_IMAGE:$VERSION $DOCKER_REGISTRY/$DOCKER_NAMESPACE/$WORKER_IMAGE:latest

echo -e "${GREEN}✓ 镜像构建完成${NC}"
echo ""

# 2. 推送镜像到仓库
echo -e "${GREEN}[2/5] 推送镜像到仓库...${NC}"

docker push $DOCKER_REGISTRY/$DOCKER_NAMESPACE/$MASTER_IMAGE:$VERSION
docker push $DOCKER_REGISTRY/$DOCKER_NAMESPACE/$MASTER_IMAGE:latest
docker push $DOCKER_REGISTRY/$DOCKER_NAMESPACE/$WORKER_IMAGE:$VERSION
docker push $DOCKER_REGISTRY/$DOCKER_NAMESPACE/$WORKER_IMAGE:latest

echo -e "${GREEN}✓ 镜像推送完成${NC}"
echo ""

# 3. 应用 K8s 配置
echo -e "${GREEN}[3/5] 应用 K8s 配置...${NC}"

# 切换到对应的集群
if [ "$ENVIRONMENT" == "test" ]; then
    kubectl config use-context test-cluster
elif [ "$ENVIRONMENT" == "prod" ]; then
    kubectl config use-context prod-cluster
else
    echo -e "${RED}错误: 未知的环境 $ENVIRONMENT${NC}"
    exit 1
fi

# 应用配置文件
echo "应用 ConfigMap..."
kubectl apply -f deployments/k8s/configmap.yaml -n $K8S_NAMESPACE

echo "应用 Secrets..."
kubectl apply -f deployments/k8s/secrets.yaml -n $K8S_NAMESPACE

echo "应用 Master Deployment..."
kubectl apply -f deployments/k8s/master-deployment.yaml -n $K8S_NAMESPACE

echo "应用 Worker Deployment..."
kubectl apply -f deployments/k8s/worker-deployment.yaml -n $K8S_NAMESPACE

echo "应用 Service..."
kubectl apply -f deployments/k8s/master-service.yaml -n $K8S_NAMESPACE

echo "应用 HPA..."
kubectl apply -f deployments/k8s/hpa.yaml -n $K8S_NAMESPACE

echo -e "${GREEN}✓ K8s 配置应用完成${NC}"
echo ""

# 4. 更新镜像
echo -e "${GREEN}[4/5] 更新镜像版本...${NC}"

kubectl set image deployment/aegis-runner-master master=$DOCKER_REGISTRY/$DOCKER_NAMESPACE/$MASTER_IMAGE:$VERSION -n $K8S_NAMESPACE
kubectl set image deployment/aegis-runner-worker worker=$DOCKER_REGISTRY/$DOCKER_NAMESPACE/$WORKER_IMAGE:$VERSION -n $K8S_NAMESPACE

echo -e "${GREEN}✓ 镜像版本更新完成${NC}"
echo ""

# 5. 等待部署完成
echo -e "${GREEN}[5/5] 等待部署完成...${NC}"

echo "等待 Master 部署完成..."
kubectl rollout status deployment/aegis-runner-master -n $K8S_NAMESPACE

echo "等待 Worker 部署完成..."
kubectl rollout status deployment/aegis-runner-worker -n $K8S_NAMESPACE

echo -e "${GREEN}✓ 部署完成${NC}"
echo ""

# 显示部署状态
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}部署状态${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

echo "Master Pods:"
kubectl get pods -l component=master -n $K8S_NAMESPACE

echo ""
echo "Worker Pods:"
kubectl get pods -l component=worker -n $K8S_NAMESPACE

echo ""
echo "Services:"
kubectl get svc -l app=aegis-runner -n $K8S_NAMESPACE

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}部署成功！${NC}"
echo -e "${GREEN}========================================${NC}"
