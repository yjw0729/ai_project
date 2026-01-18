#!/bin/bash

echo "开始更新PyTest SXP到新版本..."

# 检查是否有新的压缩包
if [ ! -f "pytest_sxp_v*.tar.gz" ]; then
    echo "错误：未找到新的版本压缩包 (pytest_sxp_v*.tar.gz)"
    echo "请确保新版本压缩包在当前目录"
    exit 1
fi

# 找到最新的版本包
LATEST_PACKAGE=$(ls -t pytest_sxp_v*.tar.gz | head -1)
echo "找到版本包: $LATEST_PACKAGE"

# 备份当前版本信息
echo "备份当前版本信息..."
docker ps --filter name=pytest-sxp --format "table {{.Names}}\t{{.Image}}\t{{.Status}}" > version_backup.txt
echo "当前版本信息已备份到 version_backup.txt"

# 解压新版本
echo "解压新版本..."
tar -xzf $LATEST_PACKAGE --strip-components=1

# 重新构建Docker镜像
echo "重新构建Docker镜像..."
docker build -t pytest-sxp:new .

# 停止旧容器
echo "停止旧版本服务..."
docker stop pytest-sxp

# 移除旧容器
docker rm pytest-sxp

# 启动新版本
echo "启动新版本服务..."
docker run -d \
  --name pytest-sxp \
  -p 8015:8015 \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/uploads:/app/uploads \
  -v $(pwd)/chroma_data:/app/chroma_data \
  -v $(pwd)/cache:/app/cache \
  --restart unless-stopped \
  pytest-sxp:new

# 标记新版本为latest
docker tag pytest-sxp:new pytest-sxp:latest

echo "更新完成！新版本已启动"
echo "应用访问地址: http://服务器IP:8015"
echo ""
echo "如果新版本有问题，可以快速回滚："
echo "docker stop pytest-sxp && docker rm pytest-sxp && ./rollback.sh"


