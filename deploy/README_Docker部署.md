# Docker部署指南

## 版本更新流程

### 1. 打包新版本（在本地开发环境）

```bash
# 确保所有更改已提交
git add .
git commit -m "版本12更新"

# 创建版本压缩包（建议包含版本号）
tar -czf pytest_sxp_v12.tar.gz --exclude='*.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='venv' .
```

### 2. 上传到服务器

```bash
# 将压缩包上传到服务器的部署目录
scp pytest_sxp_v12.tar.gz user@server:/home/app/opt/auantum-test/
```

### 3. 在服务器上更新

```bash
# 进入部署目录
cd /home/app/opt/auantum-test

# 给脚本执行权限（首次部署时）
chmod +x update_docker.sh rollback.sh

# 执行更新
./update_docker.sh
```

## 管理命令

```bash
# 查看服务状态
docker ps | grep pytest-sxp

# 查看实时日志
docker logs -f pytest-sxp

# 重启服务
docker restart pytest-sxp

# 停止服务
docker stop pytest-sxp

# 如果新版本有问题，回滚到上一版本
./rollback.sh
```

## 文件说明

- `Dockerfile` - Docker镜像构建文件
- `deploy_docker.sh` - 首次部署脚本
- `update_docker.sh` - 版本更新脚本
- `rollback.sh` - 版本回滚脚本
- `version_backup.txt` - 版本备份信息（自动生成）

## 注意事项

1. 更新时会自动备份当前版本信息
2. 新版本构建成功后，旧版本才会停止
3. 如果新版本有问题，可以立即回滚
4. 日志、上传文件、数据库数据都会保留


