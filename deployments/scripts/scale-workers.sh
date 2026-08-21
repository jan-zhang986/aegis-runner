#!/bin/bash

# Worker 扩缩容脚本

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

K8S_NAMESPACE="default"
DEPLOYMENT_NAME="aegis-runner-worker"

if [ "$1" == "" ]; then
    echo -e "${RED}错误: 请指定 Worker 数量${NC}"
    echo "用法: ./scale-workers.sh [数量]"
    echo "示例: ./scale-workers.sh 10"
    exit 1
fi

REPLICAS=$1

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Worker 扩缩容${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

echo -e "${YELLOW}当前 Worker 数量:${NC}"
kubectl get deployment $DEPLOYMENT_NAME -n $K8S_NAMESPACE -o jsonpath='{.spec.replicas}'
echo ""

echo -e "${YELLOW}目标 Worker 数量: $REPLICAS${NC}"
echo ""

read -p "确认执行扩缩容? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "操作已取消"
    exit 1
fi

echo -e "${GREEN}正在调整 Worker 数量...${NC}"
kubectl scale deployment $DEPLOYMENT_NAME --replicas=$REPLICAS -n $K8S_NAMESPACE

echo -e "${GREEN}等待 Pod 就绪...${NC}"
kubectl rollout status deployment/$DEPLOYMENT_NAME -n $K8S_NAMESPACE

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}扩缩容完成${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

echo "当前 Worker Pods:"
kubectl get pods -l component=worker -n $K8S_NAMESPACE

echo ""
echo -e "${GREEN}Worker 数量已调整为: $REPLICAS${NC}"
