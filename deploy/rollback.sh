#!/bin/bash

echo "开始回滚到上一版本..."

# 检查备份文件
if [ ! -f "version_backup.txt" ]; then
    echo "错误：未找到版本备份文件，无法回滚"
    exit 1
fi

# 显示备份信息
echo "备份的版本信息："
cat version_backup.txt

# 停止当前容器
docker stop pytest-sxp 2>/dev/null || true
docker rm pytest-sxp 2>/dev/null || true

# 启动上一版本的镜像
echo "启动上一版本..."
docker run -d \
  --name pytest-sxp \
  -p 8015:8015 \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/uploads:/app/uploads \
  -v $(pwd)/chroma_data:/app/chroma_data \
  -v $(pwd)/cache:/app/cache \
  --restart unless-stopped \
  pytest-sxp:latest

echo "回滚完成！服务已恢复到上一版本"
