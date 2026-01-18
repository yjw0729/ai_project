#!/bin/bash

echo "开始Docker部署..."

# 构建Docker镜像
docker build -t pytest-sxp .

# 停止并删除旧容器（如果存在）
docker stop pytest-sxp 2>/dev/null || true
docker rm pytest-sxp 2>/dev/null || true

# 运行新容器
docker run -d \
  --name pytest-sxp \
  -p 8015:8015 \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/uploads:/app/uploads \
  -v $(pwd)/chroma_data:/app/chroma_data \
  -v $(pwd)/cache:/app/cache \
  --restart unless-stopped \
  pytest-sxp

echo "部署完成！"
echo "应用访问地址: http://服务器IP:8015"
echo "查看日志: docker logs -f pytest-sxp"
echo "停止服务: docker stop pytest-sxp"


