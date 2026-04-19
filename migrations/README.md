# migrations/ - Alembic 数据库版本化迁移

## 用途

通过 Alembic 管理数据库 schema 版本，支持：
- `alembic revision --autogenerate -m "描述"` 自动生成迁移脚本
- `alembic upgrade head` 升级到最新版本
- `alembic downgrade -1` 回退上一版本

## 数据库

使用 `app/db_config.json` 中的 `default` 数据源。

## 迁移命令

```bash
# 生成迁移（开发时使用）
alembic revision --autogenerate -m "add user table"

# 执行迁移
alembic upgrade head

# 查看历史
alembic history

# 回退
alembic downgrade -1
```

## 注意

- 所有 ORM 模型统一使用 `common.db_enitiy` 中的 Base
- 首次使用需执行 `alembic upgrade head` 初始化版本表
