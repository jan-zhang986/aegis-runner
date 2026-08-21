#!/bin/bash

# 同步 engine 代码脚本
# 从 engine 远程仓库拉取最新代码并更新到当前仓库中

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# engine 仓库地址
AEGIS_ENGINE_REPO="https://codeup.aliyun.com/spotter/spotter/qa/aegis-engine.git"
AEGIS_ENGINE_DIR="packages/engine"
TEMP_CLONE_DIR="/tmp/aegis-engine-sync-$(date +%s)"

# 当前脚本所在目录的上上级目录（项目根目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}同步 engine 代码${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

cd "$PROJECT_ROOT"

# 检查当前 engine 目录是否存在
if [ ! -d "$AEGIS_ENGINE_DIR" ]; then
    echo -e "${RED}错误: $AEGIS_ENGINE_DIR 目录不存在${NC}"
    exit 1
fi

# 备份当前目录中的 .gitignore（如果存在）
if [ -f "$AEGIS_ENGINE_DIR/.gitignore" ]; then
    echo -e "${YELLOW}备份当前的 .gitignore...${NC}"
    cp "$AEGIS_ENGINE_DIR/.gitignore" "$AEGIS_ENGINE_DIR/.gitignore.backup"
fi

# 克隆最新代码到临时目录
echo -e "${YELLOW}[1/4] 从远程仓库拉取最新代码...${NC}"
rm -rf "$TEMP_CLONE_DIR"
git clone "$AEGIS_ENGINE_REPO" "$TEMP_CLONE_DIR" --depth 1
echo -e "${GREEN}✓ 代码拉取完成${NC}"
echo ""

# 获取最新的 commit hash
LATEST_COMMIT=$(cd "$TEMP_CLONE_DIR" && git rev-parse --short HEAD)
echo -e "${YELLOW}最新 commit: $LATEST_COMMIT${NC}"
echo ""

# 删除临时目录中的 .git 目录
echo -e "${YELLOW}[2/4] 清理临时文件...${NC}"
rm -rf "$TEMP_CLONE_DIR/.git"
echo -e "${GREEN}✓ 清理完成${NC}"
echo ""

# 备份当前 engine 目录
echo -e "${YELLOW}[3/4] 备份当前代码...${NC}"
BACKUP_DIR="$AEGIS_ENGINE_DIR.backup.$(date +%Y%m%d_%H%M%S)"
mv "$AEGIS_ENGINE_DIR" "$BACKUP_DIR"
echo -e "${GREEN}✓ 备份完成: $BACKUP_DIR${NC}"
echo ""

# 移动新代码到 engine 目录
echo -e "${YELLOW}[4/4] 更新代码...${NC}"
mv "$TEMP_CLONE_DIR" "$AEGIS_ENGINE_DIR"

# 恢复 .gitignore（如果需要保留 aegis-runner 特定的配置）
if [ -f "$BACKUP_DIR/.gitignore.backup" ]; then
    cp "$BACKUP_DIR/.gitignore.backup" "$AEGIS_ENGINE_DIR/.gitignore"
    echo -e "${GREEN}✓ 已恢复 .gitignore${NC}"
fi

echo -e "${GREEN}✓ 代码更新完成${NC}"
echo ""

# 显示变更统计
echo -e "${YELLOW}变更统计:${NC}"
if [ -d "$BACKUP_DIR" ]; then
    echo "备份位置: $BACKUP_DIR"
    echo "您可以手动检查差异: diff -r $BACKUP_DIR $AEGIS_ENGINE_DIR | head -50"
fi
echo ""

# 提示用户检查并提交
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}同步完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}下一步操作:${NC}"
echo "1. 检查变更: git status"
echo "2. 查看差异: git diff $AEGIS_ENGINE_DIR"
echo "3. 添加到暂存区: git add $AEGIS_ENGINE_DIR"
echo "4. 提交更改: git commit -m '更新 engine 到 $LATEST_COMMIT'"
echo ""
echo -e "${YELLOW}如果需要回滚:${NC}"
echo "rm -rf $AEGIS_ENGINE_DIR && mv $BACKUP_DIR $AEGIS_ENGINE_DIR"
echo ""
