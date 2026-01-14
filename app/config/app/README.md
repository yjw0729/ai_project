# 应用配置

## 📋 概述

本目录包含Flask应用的配置文件，包括数据库连接、AI服务配置等。

## 📁 文件说明

- **`ai_config.json`** - AI服务相关配置
- **`db_config.json`** - 关系型数据库配置
- **`yjw_ai_config.json`** - 业务AI配置
- **`application.xml`** - 应用启动配置

## 🔧 配置说明

### AI配置 (ai_config.json)

```json
{
  "openai": {
    "api_key": "your-openai-key",
    "base_url": "https://api.openai.com/v1",
    "timeout": 30
  },
  "model_settings": {
    "temperature": 0.7,
    "max_tokens": 2000
  }
}
```

### 数据库配置 (db_config.json)

```json
{
  "host": "localhost",
  "port": 3306,
  "database": "test_agent",
  "username": "user",
  "password": "password",
  "charset": "utf8mb4"
}
```

### 应用配置 (application.xml)

XML格式的应用启动配置，包含：
- 服务器端口
- 调试模式
- 日志配置
- 安全设置

