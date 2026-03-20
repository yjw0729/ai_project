# 部署工具箱

这个目录包含了PyTest SXP项目的完整部署工具链。

## 📁 文件结构

```
deploy/
├── Dockerfile                    # Docker镜像构建配置
├── deploy_docker.sh             # 首次部署脚本
├── update_docker.sh             # 版本更新脚本
├── rollback.sh                  # 版本回滚脚本
├── test_embedding_models.py     # 向量化模型测试脚本
├── test_business_modules.py     # 业务模块功能测试脚本
├── test_visualization_api.py    # 3D可视化API测试脚本
├── README_Docker部署.md         # Docker部署详细指南
├── README_多模型向量化.md       # 多模型向量化功能说明
├── README_业务模块功能.md       # 业务模块功能详细指南
├── README_3D向量可视化.md       # 3D向量可视化功能详细指南
└── README.md                   # 本文件
```

## 🚀 快速开始

### 首次部署
```bash
# 1. 安装Docker
sudo apt install docker.io  # Ubuntu/Debian
# 或
sudo yum install docker     # CentOS/RHEL

# 2. 运行部署脚本
./deploy_docker.sh
```

### 版本更新
```bash
# 1. 上传新版本压缩包到项目根目录
# 2. 运行更新脚本
./update_docker.sh
```

### 版本回滚（如有问题）
```bash
./rollback.sh
```

## 🧪 测试功能

### 测试多模型向量化
```bash
python test_embedding_models.py
```

### 测试业务模块功能
```bash
python test_business_modules.py
```

### 测试3D可视化功能
```bash
python test_visualization_api.py
```

## 📋 功能特性

- ✅ **一键部署**: 简单的Docker容器化部署
- ✅ **智能更新**: 自动备份和回滚机制
- ✅ **多模型支持**: 根据文档类型自动选择最适合的向量化模型
- ✅ **业务模块化**: 支持按业务模块（跨境开户/交易、互联网开户/交易）分类管理
- ✅ **精确检索**: 支持按业务模块过滤查询，实现更精准的文档检索
- ✅ **3D可视化**: 支持向量数据的2D/3D降维可视化（UMAP/T-SNE）
- ✅ **环境隔离**: Docker容器保证环境一致性
- ✅ **数据持久化**: 日志、上传文件、向量数据库自动持久化

## 🔧 高级配置

- 查看 `README_Docker部署.md` 了解详细的部署流程
- 查看 `README_多模型向量化.md` 了解智能向量化配置
- 查看 `README_业务模块功能.md` 了解业务模块分类和查询功能
- 查看 `README_3D向量可视化.md` 了解3D向量可视化功能和前端集成

## 📞 支持

如有问题，请查看相应的README文档或检查日志：
```bash
docker logs -f pytest-sxp
```
