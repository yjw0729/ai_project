# pytest_sxp 开发指南

> 本文档定义项目代码的存放规范和编写规则。所有新功能开发、模块扩展、配置修改均应遵循本指南。
> 文档日期：2026-04-19

---

## 一、目录存放总则

### 1.1 核心原则

项目代码分为 **app 层** 和 **common 层** 两部分，遵循以下核心原则：

| 原则 | 说明 |
|---|---|
| **common 优先** | 所有可复用的业务逻辑、数据结构、工具必须放在 `common/` 下 |
| **app 专用** | 只有 Flask HTTP 入口（Blueprint）、应用级配置、静态资源放在 `app/` 下 |
| **禁止反向依赖** | `app/` 可以引用 `common/`，但 `common/` 不得引用 `app/` |
| **单一职责** | 每个 `.py` 文件不超过 500 行，超出则拆分 |
| **不重复** | 相同功能只应有一处实现，发现重复代码应合并而非继续复制 |

### 1.2 目录职责速查表

| 如果你要开发… | 存放位置 | 备注 |
|---|---|---|
| 新的 HTTP API 端点 | `app/views/blueprint_xxx.py` | 每个文件一个 Blueprint |
| LLM 调用相关 | `common/llm/` | llm_client / prompt_manager 已覆盖 |
| 新的文档解析逻辑 | `common/document/processors/` | 参考 `api_doc_processor.py` |
| 新的文档切分策略 | `common/document/chunkers/` | 参考 `prd_doc_chunker.py` |
| 新的数据断言验证器 | `common/assertion/validators.py` | 在 `AssertionType` 枚举后追加 |
| AI 断言生成 | `common/assertion/auto_generator.py` | 参照 `SmartAssertionGenerator` |
| 数据库 CRUD | `common/db/mapper/` + `common/db/entity/` | 实体 + Mapper 配套添加 |
| 业务服务逻辑 | `common/services/` | 跨多个 Mapper 的业务编排 |
| 测试执行相关 | `common/test_executor/` | api_test_runner 已覆盖大部分场景 |
| Worker 任务处理 | `common/worker/task_processor.py` | 注册新的 task_type 分发函数 |
| 异步任务队列 | `platform_service/service/` | TaskService + MQClient |
| 测试数据生成器 | `utils/auto_generate/` | 参照现有 generate_customer.py |
| 共享数据模型 | `common/models/` | dataclass + 枚举，配套 Pydantic schemas |
| 配置参数 | `common/config/` + `app/xxx_config.json` | 区分通用配置和应用配置 |
| Prompt 模板 | `app/prompts.yaml` | 按类别（test_case_generation 等）追加 |
| Pytest Fixtures | `common/pytest/fixtures/` | `api_client.py` / `auth.py` 等 |
| 项目自身测试 | `common/pytest/tests/` | `tests/` 目录仅保留入口引用 |
| 运维脚本 | `scripts/` | 启动、检查等非核心脚本 |
| 一次性验证脚本 | 项目根目录（临时） | 确认后删除或移入 `scripts/` |

---

## 二、各模块编写规范

### 2.1 Flask Blueprint（`app/views/`）

每个 Blueprint 为一个独立文件，放在 `app/views/` 下，命名为 `blueprint_功能名.py`。

**文件模板：**

```python
"""
blueprint_xxx.py — 功能描述

API: /api/xxx (GET/POST/PUT/DELETE)
"""
from flask import Blueprint, request, jsonify
from common.xxx import SomeService  # common 层引用

xxx_bp = Blueprint("xxx", __name__)


@xxx_bp.route("/action", methods=["POST"])
def do_something():
    """
    接口描述

    Request Body:
        {"param": "value"}

    Returns:
        {"code": 200, "data": {...}}
    """
    payload = request.get_json(silent=True) or {}
    # ... 业务逻辑
    return jsonify({"code": 200, "data": result, "message": "success"})
```

**在 `app/views/__init__.py` 中注册：**

```python
from app.views.blueprint_xxx import xxx_bp
# 在 create_app() 中添加：
# flask_app.register_blueprint(xxx_bp, url_prefix="/api/xxx")
```

**规范：**
- 每个 Blueprint 不超过 5 个路由，超出则拆分为多个 Blueprint
- 禁止在 Blueprint 中直接写 SQL，应调用 `common/db/mapper/` 中的 Mapper
- HTTP 响应统一格式：`{"code": 200/400/500, "data": ..., "message": "..."}`
- 大文件上传用 `request.files`，小参数用 `request.get_json()`
- 所有 Blueprint 在 `app/views/__init__.py` 中集中导出

### 2.2 LLM 调用（`common/llm/`）

**使用 llm_client：**

```python
from common.llm.llm_client import LLMClient

client = LLMClient(model="qwen-plus")
response = client.chat(
    messages=[{"role": "user", "content": "请生成测试用例"}],
    temperature=0.7,
    max_tokens=2000,
)
```

**添加 Prompt 模板：**
1. 在 `app/prompts.yaml` 中追加：

```yaml
new_category:
  description: "新功能描述"
  system: |
    你是一个专业的测试工程师...
  user: |
    请根据以下文档内容生成...
```

2. 在 `prompt_manager.py` 中添加 getter：

```python
def get_new_category_prompt(self, **kwargs) -> str:
    """获取新功能 Prompt"""
    template = self.prompts.get("new_category", {})
    return template.get("user", "").format(**kwargs)
```

**规范：**
- LLM 调用统一经 `llm_client.py`，禁止直接调用 DashScope API
- 所有 Prompt 模板放在 `app/prompts.yaml`，不在代码中硬编码大段 Prompt
- Mock 模式：`LLM_MOCK_MODE=1` 环境变量用于离线开发
- Token 费用敏感场景：使用 `tiktoken` 预估后设置 `max_tokens`

### 2.3 文档处理（`common/document/`）

**新增文档处理器（按类型）：**

```
common/document/processors/
    └── processor_xxx.py   # 新处理器
```

```python
from common.document.core.models import DocumentType
from common.document.processors.base_processor import BaseProcessor  # 参考现有结构

class XxxDocProcessor(BaseProcessor):
    """Xxx 类型文档处理器"""
    SUPPORTED_TYPES = [DocumentType.XXX]

    def process(self, document: Document) -> Document:
        # 1. 提取结构
        # 2. 内容清洗
        # 3. 分块
        return document
```

**在统一入口注册：**

```python
# common/document/processors/unified_processor.py
from common.document.processors.processor_xxx import XxxDocProcessor

class UnifiedDocumentProcessor:
    def __init__(self):
        self._processors = {
            DocumentType.API_DESIGN: APIDocumentProcessor(),
            DocumentType.PRODUCT_DESIGN: ProductDocProcessor(),
            DocumentType.XXX: XxxDocProcessor(),  # 新增
        }
```

**新增切分器（`chunkers/`）：**

```python
# common/document/chunkers/xxx_doc_chunker.py
class XxxDocChunker:
    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str) -> list[DocumentChunk]:
        ...
```

### 2.4 断言引擎（`common/assertion/`）

**新增断言验证器：**

在 `common/assertion/validators.py` 中追加 `AssertionType` 枚举值和对应验证函数：

```python
# 在 AssertionType 枚举中追加
class AssertionType(str, Enum):
    # ... 现有类型
    NEW_TYPE = "new_type"  # 新断言类型

# 在 _VALIDATORS dict 中追加
_VALIDATORS = {
    # ... 现有验证器
    AssertionType.NEW_TYPE: _validate_new_type,
}

def _validate_new_type(field: str, expected, actual, **kwargs) -> AssertionResult:
    # 验证逻辑
    return AssertionResult(...)
```

**AI 自动断言：**

在 `auto_generator.py` 中扩展 `SmartAssertionGenerator` 的生成策略。

### 2.5 数据库层（`common/db/`）

**新增 Entity：**

```
common/db/entity/
    └── new_entity.py    # SQLAlchemy ORM 类
common/db/mapper/
    └── new_entity_mapper.py  # CRUD 操作
```

**Entity 模板：**

```python
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base
from common.db.datacase.contect_db import Base
from datetime import datetime

class NewEntity(Base):
    __tablename__ = "crosstest_new_entity"
    __table_args__ = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, comment="名称")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    # 在此添加 @classmethod 工厂方法
    @classmethod
    def create(cls, session, **kwargs):
        ...
```

**Mapper 模板：**

```python
from typing import Optional
from common.db.datacase.contect_db import db_session

class NewEntityMapper:
    @staticmethod
    def insert(session, entity) -> int:
        session.add(entity)
        session.flush()
        return entity.id

    @staticmethod
    def find_by_id(session, entity_id: int) -> Optional[Entity]:
        return session.query(Entity).filter(Entity.id == entity_id).first()

    @staticmethod
    def update(session, entity_id: int, **kwargs) -> bool:
        ...
```

### 2.6 业务服务层（`common/services/`）

服务层用于编排多个 Mapper 或封装复杂业务逻辑：

```python
# common/services/new_service.py
from common.db.mapper.new_entity_mapper import NewEntityMapper
from common.llm.llm_client import LLMClient
from common.config import load_ai_config

class NewService:
    def __init__(self):
        self.mapper = NewEntityMapper()
        self.llm = LLMClient(model="qwen-plus")

    def do_something(self, session, param: str) -> dict:
        # 1. 查数据库
        entity = self.mapper.find_by_id(session, param)
        # 2. 调 LLM
        result = self.llm.chat(...)
        # 3. 写回
        self.mapper.update(session, entity.id, result=result)
        return result
```

### 2.7 测试执行引擎（`common/test_executor/`）

**新增执行模式：**

在 `api_test_runner.py` 中添加新的执行模式（串行/并行/链式），或扩展 `ParameterResolver` 的变量类型。

**扩展变量替换：**

```python
# common/test_executor/parameter_resolver.py

# 在 SPECIAL_GENERATORS dict 中追加
SPECIAL_GENERATORS = {
    # ... 现有生成器
    "{{new_generator}}": lambda ctx: generate_new_value(ctx),
}
```

**新增 DB 断言操作符：**

```python
# common/test_executor/db_field_validator.py
OPERATORS = {
    # ... 现有操作符
    "new_operator": lambda a, b: a > b,  # 示例
}
```

### 2.8 Worker 系统（`common/worker/`）

**新增任务类型：**

```python
# common/worker/task_processor.py
from common.models.task import TaskType

def process_new_task(payload: dict, context: dict) -> dict:
    """处理新类型任务"""
    ...

# 在 TaskProcessor.__init__ 中注册
self._handlers = {
    # ... 现有 handlers
    TaskType.NEW_TYPE: process_new_task,
}
```

### 2.9 共享数据模型（`common/models/`）

```python
# common/models/new_model.py
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class NewStatus(str, Enum):
    PENDING = "pending"
    DONE = "done"

@dataclass
class NewModel:
    id: str
    status: NewStatus = NewStatus.PENDING
    metadata: dict = field(default_factory=dict)

    def is_valid(self) -> bool:
        return bool(self.id)
```

### 2.10 Pytest Fixtures（`common/pytest/fixtures/`）

**新增 Fixture：**

```python
# common/pytest/fixtures/new_fixture.py
import pytest

@pytest.fixture
def new_fixture(app_config):
    """新 Fixture 描述"""
    # setup
    value = compute_value()
    yield value
    # teardown
    cleanup_value()
```

**在 `conftest.py` 中注册：**

```python
# common/pytest/fixtures/conftest.py
from common.pytest.fixtures.new_fixture import new_fixture
# pytest_plugins 由 fixtures/conftest.py 统一聚合
```

---

## 三、配置文件存放规范

### 3.1 配置文件一览

| 配置文件 | 位置 | 用途 | 加载方式 |
|---|---|---|---|
| DashScope API Key | `app/ai_config.json` | LLM 调用 | `app/__init__.py` 启动时加载 |
| 全局执行配置 | `app/api_auto_test_config.json` | 超时/并发/重试策略 | `ConfigLoader` |
| 数据库数据源 | `app/db_config.json` | 3 个 MySQL 连接信息 | `SQLAlchemy Engine` |
| Prompt 模板 | `app/prompts.yaml` | LLM Prompt 管理 | `PromptManager`（Singleton） |
| 应用元信息 | `app/application.xml` | 端口、日志路径等 | `read_xml()` |
| SQL 语句定义 | `common/config/sql_config.json` | 预定义 SQL 查询 | `load_config("sql_config.json")` |
| RAG 向量配置 | `app/config/rag/rag.json` | Embedding 模型/参数 | 未被引用（预留） |
| 断言模板 | `app/assertion_templates.yaml` | 预定义断言规则 | — |

### 3.2 新增配置规范

| 配置类型 | 存放在 | 命名规范 |
|---|---|---|
| 与 Flask App 强相关（Key/Port/XML） | `app/` | `xxx_config.json` 或 `xxx.yaml` |
| 与业务逻辑相关（超时/并发/重试） | `app/api_auto_test_config.json` | 追加 key |
| 跨模块通用配置 | `common/config/` | `xxx_config.json` |
| Prompt 模板 | `app/prompts.yaml` | 按 category 追加 |
| SQL 语句 | `common/config/sql_config.json` | 按 category 追加 |

**禁止**：
- 不要在代码中硬编码配置值
- 不要创建同功能的多份配置（发现后合并）
- 不要在 `app/` 下创建 Python 业务逻辑文件（除 `views/` 和 `run.py`）

---

## 四、命名规范

| 对象 | 命名规则 | 示例 |
|---|---|---|
| Blueprint | `blueprint_功能名.py` | `blueprint_test_case_generate.py` |
| Entity 类 | `PascalCase` | `TestCase`, `ReviewSummary` |
| Mapper 类 | `XxxMapper` | `TestCaseMapper`, `ReviewSummaryMapper` |
| Service 类 | `XxxService` | `AssertionService`, `DocumentParserService` |
| 枚举 | `PascalCase` | `TaskStatus`, `HttpMethod` |
| 变量 | `snake_case` | `test_case_id`, `execution_result` |
| 常量 | `UPPER_SNAKE_CASE` | `MAX_RETRY_TIMES`, `DEFAULT_TIMEOUT` |
| 私有方法 | `_snake_case` | `_validate_params()` |
| Blueprint 变量 | `xxx_bp` | `test_case_gen_opt`, `api_auto_test_bp` |
| 文件名 | `snake_case.py` | `test_case_executor.py` |

---

## 五、依赖规则

```
┌─────────────────────────────────┐
│  HTTP Client (用户请求)          │
└────────────┬────────────────────┘
             ▼
┌─────────────────────────────────┐
│  app/views/ (Blueprint)          │  ← 唯一允许接收 HTTP 请求的地方
│  app/run.py (入口)               │
└────────────┬────────────────────┘
             ▼
┌─────────────────────────────────┐
│  common/ (核心业务代码)           │
│  · llm/                        │
│  · db/                         │
│  · services/                   │
│  · test_executor/              │
│  · document/                   │
│  · assertion/                  │
│  · worker/                     │
│  · models/                     │
│  · mq/                         │
│  · config/                     │
│  · pytest/                     │
│  · business_context/           │
│  · error_code/                 │
└─────────────────────────────────┘

依赖方向：
  app/  ──────► common/
  workers/ ───► common/
  scripts/ ───► common/
  tests/ ─────► common/

禁止方向（反向依赖）：
  common/ ──✗──► app/
  common/ ──✗──► workers/
```

---

## 六、代码组织检查清单

在提交代码前，确认以下事项：

- [ ] 新功能是否放在 `common/` 下（可复用部分）？
- [ ] 是否在正确的子目录下（参照"目录职责速查表"）？
- [ ] 新增配置是否在对应的 `xxx_config.json` 中？
- [ ] 新增 Prompt 是否在 `app/prompts.yaml` 中？
- [ ] 新增数据库 Entity 是否配套了 Mapper？
- [ ] 是否避免了与现有文件的代码重复？
- [ ] 文件是否超过 500 行（需要拆分）？
- [ ] 是否遵循了命名规范？
- [ ] `common/` 模块是否可以独立导入（不依赖 `app/`）？
- [ ] 是否有对应的 pytest fixture 和测试用例？

---

## 七、当前待清理问题（重构时参考）

| 问题 | 说明 | 建议处理 |
|---|---|---|
| `app/views/*.py` 缺失 | git 已删但 pycache 残留 | 需从 git 历史恢复或重写 |
| `common/rag/` 残留 | 24 个文件，功能已迁至 `common/document/` | 删除整目录（确认无引用后） |
| `utils/error_code/` 重复 | 与 `common/error_code/` 完全相同 | 删除 `utils/error_code/`，统一引用 |
| `core/runner.py` 未被引用 | 独立构建的执行引擎 | 评估是否使用，使用则迁移，废弃则删除 |
| `common/config/sql_config.json` 缺失 | P1 问题：被引用但文件不存在 | 补充该文件 |

---

*文档生成日期：2026-04-19*
