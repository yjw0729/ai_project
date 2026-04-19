# pytest_sxp - AI 驱动自动化测试平台

> 本文档为项目主文档，涵盖项目定位、技术栈、架构设计、各模块职责、运行方式及数据流向。
> 扫描日期：2026-04-19

---

## 一、项目定位

**pytest_sxp** 是一个基于 Python + Flask + 通义千问（DashScope LLM）的 AI 驱动自动化测试平台。平台从技术文档（API 文档、PRD、设计文档）自动生成测试用例，管理测试套件与执行计划，并运行接口自动化测试，输出 Allure 报告。

核心能力链路：

```
技术文档（DOCX/PDF/Confluence）
    → 文档分类 → LLM 提取接口/需求 → 测试用例生成 → 去重验证
    → MySQL 用例库存储
    → 参数化执行 → HTTP 请求 → 断言验证 → Allure 报告
```

---

## 二、技术栈

| 层次 | 技术选型 | 说明 |
|---|---|---|
| Web 框架 | Flask + gevent | 生产环境用 gevent WSGI server |
| 数据库 | SQLAlchemy + PyMySQL / MySQL × 3 | 13 张 `crosstest_*` 表 |
| 任务队列 | RabbitMQ（pika）+ SQLite（降级） | Workers 异步消费 |
| 缓存 | Redis | 任务状态缓存（24h TTL） |
| AI/LLM | 通义千问 DashScope | qwen-plus / qwen-max / qwen-vl / qwen-coder |
| 测试框架 | pytest + pytest-rerunfailures + Allure | 支持标记、并行、重跑 |
| 文档解析 | pdfplumber / python-docx / openpyxl | 文档切分用 tiktoken |
| 数据模型 | Pydantic（MQ schemas）+ dataclass | 输入验证 |
| 迁移 | Alembic | 数据库版本管理 |
| 配置 | JSON + YAML + XML（application.xml） | 多格式配置加载 |

---

## 三、目录结构

```
pytest_sxp/
├── app/                          # Flask 应用（应用工厂 + Blueprint）
│   ├── __init__.py               # create_app() 工厂函数
│   ├── run.py                    # 备用启动脚本（含端口清理）
│   ├── extensions.py             # Flask 日志配置
│   ├── ai_config.json           # DashScope API Key 配置
│   ├── api_auto_test_config.json # 测试执行全局配置
│   ├── application.xml           # 应用配置（端口、日志路径等）
│   ├── db_config.json            # 3 个 MySQL 数据源配置
│   ├── prompts.yaml              # LLM Prompt 模板（YAML 格式）
│   ├── views/                    # Flask Blueprint（20 个端点）
│   │   ├── blueprint_test_case_generate.py   # 文档 → 用例生成（核心）
│   │   ├── blueprint_api_auto_test.py        # API 自动化执行（核心）
│   │   ├── blueprint_ai_doc_parser.py        # AI 文档解析
│   │   ├── blueprint_ai_generate_cases.py    # AI 用例生成
│   │   ├── blueprint_enhanced_generate_cases.py  # 增强版生成
│   │   ├── blueprint_document_comparison.py   # 文档对比
│   │   ├── blueprint_page_test_case.py       # 页面级用例（OCR）
│   │   ├── blueprint_api_interface_xmind.py  # XMind 格式导入
│   │   ├── blueprint_test_case_import.py     # 外部格式导入
│   │   ├── blueprint_test_execution.py        # 测试执行管理
│   │   ├── blueprint_test_suite.py            # 测试套件管理
│   │   ├── blueprint_ai_generate_cases.py     # 用例生成
│   │   ├── blueprint_data_generate.py        # 数据生成服务
│   │   ├── blueprint_data_factory.py         # 测试数据工厂
│   │   ├── blueprint_api_config.py            # API 接口配置 CRUD
│   │   ├── blueprint_database_config.py      # 数据库连接配置
│   │   ├── blueprint_environment_config.py    # 环境配置 CRUD
│   │   ├── blueprint_assertions.py            # 断言管理
│   │   └── blueprint_tasks.py                 # 异步任务管理
│   ├── config/                      # 静态配置文件（JSON）
│   │   └── rag/                     # RAG 配置（预留）
│   ├── templates/                    # Jinja2 模板（CSV 导入模板等）
│   ├── data/                        # 运行时数据目录
│   │   └── test_case_imports/       # 用例导入文件
│   ├── outputs/                     # 执行输出（Allure 结果、生成的测试文件）
│   │   ├── allure-results/          # Allure 原始结果
│   │   ├── generated_tests/         # 动态生成的 pytest 文件
│   │   ├── page_test_cases/         # 页面用例导出
│   │   └── comparison_results/       # 文档对比结果
│   └── uploads/                     # 用户上传文件暂存（按 UUID 组织）
│
├── common/                          # 核心业务代码（与 app 解耦，可独立引用）
│   ├── llm/                         # LLM 调用层
│   │   ├── llm_client.py           # DashScope HTTP 客户端（流式/批处理/Mock）
│   │   ├── prompt_manager.py        # YAML Prompt 模板管理器（Singleton）
│   │   ├── doc_parser.py            # PDF/DOCX → 结构化字段提取
│   │   ├── ai_case_generator.py     # LLM 批量生成用例
│   │   ├── api_doc_analyzer.py      # OpenAPI/Swagger/流程图解析
│   │   └── enhanced_case_generator.py  # 增强版生成（结合业务上下文）
│   │
│   ├── document/                    # 文档处理（新版本，已重构）
│   │   ├── core/
│   │   │   ├── models.py            # Document/DocumentChunk dataclass + 枚举
│   │   │   ├── document_processor.py # 文档处理器（切分/去重/清洗）
│   │   │   ├── data_collector.py     # 多源文档收集
│   │   │   ├── smart_document_processor.py  # 智能处理
│   │   │   └── word_document_processor.py    # Word 文档处理
│   │   ├── processors/              # 专用处理器（按文档类型）
│   │   │   ├── unified_processor.py  # 统一入口（自动识别类型并分发）
│   │   │   ├── document_classifier.py  # 文档类型分类器
│   │   │   ├── api_doc_processor.py   # API 文档处理器
│   │   │   ├── product_doc_processor.py  # PRD 文档处理器
│   │   │   ├── adaptive_processor.py  # 自适应处理器
│   │   │   ├── content_enhancer.py    # 内容增强
│   │   │   ├── multi_level_parser.py  # 多级解析
│   │   │   └── api_auto_test_processor.py  # 自动测试用文档处理
│   │   ├── chunkers/                # 领域专用切分器
│   │   │   ├── prd_doc_chunker.py    # PRD 切分
│   │   │   └── test_doc_chunker.py   # 测试文档切分
│   │   ├── connectors/               # 文档来源连接器
│   │   │   ├── file_connector.py      # 本地文件
│   │   │   ├── database_connector.py  # 数据库
│   │   │   └── conflunce_connector.py # Confluence
│   │   └── utils/
│   │       ├── api_doc_parser.py     # API 文档解析工具
│   │       └── xmind_generator.py     # XMind 导出工具
│   │
│   ├── test_executor/               # 测试执行引擎
│   │   ├── api_test_runner.py       # APITestRunner（串行/并行执行）
│   │   ├── parameter_resolver.py     # 变量替换引擎（全局/PREV/生成器/DB查询）
│   │   ├── fixture_manager.py        # Fixture 注册表
│   │   ├── pytest_generator.py       # 动态 .py 测试文件生成
│   │   ├── pytest_generator_suite.py  # 套件级 pytest 生成
│   │   ├── db_query_executor.py      # 多数据源 SQL 执行器
│   │   ├── db_check_runner.py        # post_script + db_checks 编排
│   │   ├── db_field_validator.py     # 14 种字段断言操作符
│   │   ├── db_check_parser.py        # post_script/db_checks 配置解析
│   │   ├── response_extract.py       # 响应字段提取
│   │   ├── test_case_executor.py      # 用例 → 执行数据 pipeline
│   │   └── expected_results.py        # expected_results 格式解析
│   │
│   ├── services/                    # 业务服务层
│   │   ├── assertion_engine.py       # 断言引擎（服务封装）
│   │   ├── case_generator.py         # 测试用例生成服务
│   │   ├── data_factory.py           # 测试数据工厂（姓名/手机/身份证/银行卡等）
│   │   └── document_parser.py        # LLM 辅助文档解析
│   │
│   ├── assertion/                   # 断言核心（已从 services 迁移）
│   │   ├── validators.py            # 10 种验证器
│   │   │                            #   StatusCode / JsonPath / Contains /
│   │   │                            #   Schema / ResponseTime / Header /
│   │   │                            #   Regex / Length / Type / NotEmpty
│   │   └── auto_generator.py        # 自动断言生成 + AI 智能断言
│   │
│   ├── db/                          # 数据库层（SQLAlchemy ORM）
│   │   ├── entity/                  # ORM 实体（13 张表）
│   │   │   ├── test_case.py        # crosstest_test_case（含优先级/状态/评审流程）
│   │   │   ├── test_execution.py   # crosstest_test_execution
│   │   │   ├── test_suite.py       # crosstest_test_suite
│   │   │   ├── test_suite_case.py  # crosstest_test_suite_case
│   │   │   ├── test_plan.py        # crosstest_test_plan
│   │   │   ├── api_config.py       # crosstest_api_config
│   │   │   ├── database_config.py  # crosstest_database_config
│   │   │   ├── environment_config.py  # crosstest_environment_config
│   │   │   ├── global_variable.py   # crosstest_global_variable
│   │   │   ├── review_record.py    # crosstest_review_record
│   │   │   ├── review_summary.py   # crosstest_review_summary
│   │   │   ├── task_execution.py    # crosstest_task_execution
│   │   │   └── business_context.py  # crosstest_business_context
│   │   ├── mapper/                 # Mapper CRUD（13 个，对应 13 张表）
│   │   └── datacase/
│   │       ├── contect_db.py       # SQLAlchemy Engine/Session 工厂（连接池）
│   │       └── read_datebase.py    # PyMySQL 原始查询
│   │
│   ├── worker/                     # Worker 抽象层
│   │   ├── task_poller.py          # SQLite 任务轮询（分布式抢锁）
│   │   ├── task_processor.py       # 任务分发（按 task_type）
│   │   ├── test_worker.py          # Thread 基础 TestWorker
│   │   └── worker_pool.py          # Process 基础 WorkerPool（cpu×2+1）
│   │
│   ├── models/                     # 共享数据模型
│   │   ├── task.py                 # Task dataclass + 枚举
│   │   ├── assertion.py            # 断言配置（SQLite CRUD）
│   │   ├── document.py             # Document dataclass + 枚举
│   │   ├── interface.py            # Interface dataclass + 枚举
│   │   └── test_data.py            # TestDataConfig dataclass
│   │
│   ├── mq/                        # 消息队列协议
│   │   ├── schemas.py             # Pydantic 模型（TaskStatus/TaskType/Request/Response）
│   │   ├── mq_messages.py         # MQMessage + MQQueueConfig
│   │   └── trace.py               # TraceContext + LogFormatter
│   │
│   ├── config/                    # 统一配置加载
│   │   ├── __init__.py            # load_config / get_sql_config / read_xml / load_ai_config
│   │   └── sql_config.json        # SQL 查询语句定义
│   │
│   ├── pytest/                   # Pytest 集成
│   │   ├── fixtures/              # Pytest Fixtures
│   │   │   ├── conftest.py       # Fixture 聚合入口
│   │   │   ├── api_client.py     # HTTP 客户端（含自动重试 3 次）
│   │   │   ├── auth.py           # 认证 Token
│   │   │   ├── database.py      # DB 连接
│   │   │   └── cleanup.py        # 资源清理
│   │   └── tests/               # 项目自身测试
│   │       ├── conftest.py       # 全局 fixtures + pytest hooks
│   │       ├── test_assertion_engine.py   # 断言引擎测试
│   │       ├── test_db_assertion.py       # DB 断言测试
│   │       ├── test_generate_testcases_from_doc.py  # 集成测试
│   │       └── unit/test_worker.py        # Worker 单元测试
│   │
│   ├── business_context/         # 业务上下文管理
│   │   └── context_manager.py    # LLM 辅助内容清洗（OCR 修正/结构化提取）
│   │
│   └── error_code/               # 错误码库
│       └── error_code_library.py # ErrorCodeLibrary（JSON 加载）
│
├── workers/                      # Worker 进程
│   ├── run_worker.py             # CLI 入口（多进程 WorkerPool）
│   ├── start_workers.py         # 统一启动脚本（健康检查 + 优雅退出）
│   └── mq_consumer.py           # RabbitMQ 消费端（Redis Pub/Sub 进度推送）
│
├── migrations/                  # Alembic 数据库迁移
│   ├── env.py                   # 迁移环境配置
│   └── versions/                # 迁移版本脚本
│       ├── 001_initial.py      # 创建 13 张 crosstest_* 表
│       ├── add_extract_fields.py  # 为 test_case 新增 extract_fields 列
│       └── add_missing_suite_case_columns.py  # 为 suite_case 新增 12 列
│
├── scripts/                    # 运维脚本
│   ├── start_services.py       # 多服务启动（Redis/RabbitMQ/MySQL/Flask/Workers）
│   ├── run_smoke_tests.py      # 冒烟测试（--parallel --workers）
│   ├── run_ci_tests.py         # CI 测试（--marker --parallel）
│   └── run_tests.py            # Worker 单元测试入口
│
├── platform_service/           # 平台服务层（Redis + MySQL 双写任务管理）
│   └── service/
│       ├── task_service.py     # create_task / get_status（Redis → MySQL 降级）
│       ├── mq_client.py        # RabbitMQ 发布/消费单例
│       ├── rate_limiter.py     # 限流存根（预留）
│       └── async_api_helpers.py  # Flask Blueprint 懒加载封装
│
├── utils/                      # 工具函数
│   ├── auto_generate/          # 测试数据生成器（12 个生成器）
│   ├── csv_function/           # CSV/YAML 读写
│   ├── datacase_function/      # 数据库操作（SQLAlchemy + PyMySQL）
│   ├── data_structures/        # 数据结构（ReviewData）
│   ├── error_code/             # 错误码库（与 common/error_code/ 重复）
│   └── image_analysis/         # 图片 OCR 分析
│
├── examples/                   # API 示例脚本
├── parametrize/                # 数据驱动测试框架
├── mock_service/               # MockServer
├── core/                       # 独立构建的 pytest 执行引擎（未被引用）
├── db/                         # SQLite 任务队列初始化
├── infrastructure/             # 基础设施配置
│   └── rabbitmq/docker-compose.yml  # RabbitMQ Docker 配置
│
├── requirements.txt            # Python 依赖清单
├── pytest.ini                  # Pytest 全局配置（markers / testpaths / timeout）
├── alembic.ini                 # Alembic 配置
├── conftest.py                 # 根级 pytest hook（sessionfinish 写结果）
├── run.py                      # 生产环境入口
└── run_tests.py                # 单元测试入口
```

---

## 四、架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                      HTTP Clients                               │
└─────────────────────────┬───────────────────────────────────────┘
                          │ POST / GET
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│  app/__init__.py (create_app)                                    │
│  app/views/  Blueprint × 20                                       │
│  ├── blueprint_test_case_generate.py    (文档 → 用例生成)          │
│  ├── blueprint_api_auto_test.py         (API 执行)                │
│  ├── blueprint_ai_doc_parser.py         (文档解析)                │
│  ├── blueprint_test_execution.py        (执行管理)                │
│  ├── blueprint_test_suite.py            (套件管理)                 │
│  ├── blueprint_ai_generate_cases.py     (AI 生成)                 │
│  ├── blueprint_enhanced_generate_cases.py (增强生成)              │
│  ├── blueprint_document_comparison.py   (文档对比)                │
│  ├── blueprint_page_test_case.py        (页面用例)                │
│  ├── blueprint_api_interface_xmind.py   (XMind 导入)              │
│  ├── blueprint_test_case_import.py      (外部导入)                 │
│  ├── blueprint_data_factory.py          (数据工厂)                 │
│  ├── blueprint_api_config.py            (API 配置)                │
│  ├── blueprint_database_config.py        (DB 配置)                 │
│  ├── blueprint_environment_config.py      (环境配置)                │
│  ├── blueprint_assertions.py             (断言管理)                 │
│  ├── blueprint_tasks.py                  (异步任务)                 │
│  └── blueprint_data_generate.py          (数据生成)                 │
└────────────┬─────────────────┬──────────────────┬──────────────────┘
             │                 │                  │
             ▼                 ▼                  ▼
┌─────────────────┐  ┌──────────────────┐  ┌─────────────────────────┐
│  common/llm/     │  │  common/db/      │  │  common/test_executor/  │
│  · llm_client   │  │  · entity/       │  │  · api_test_runner      │
│  · prompt_mgr   │  │  · mapper/       │  │  · parameter_resolver   │
│  · doc_parser   │  │  · datacase/      │  │  · fixture_manager      │
└─────────────────┘  └──────────────────┘  └─────────────────────────┘

             │                 │                  │
             ▼                 ▼                  ▼
┌──────────────────────────────────────────────────────────────────┐
│  common/document/            common/services/    common/worker/  │
│  · unified_processor         · assertion_engine   · task_poller  │
│  · api_doc_processor         · case_generator     · task_processor│
│  · product_doc_processor     · data_factory       · worker_pool   │
│  · document_classifier       · document_parser    · test_worker  │
└──────────────────────────────────────────────────────────────────┘

   ↓ (MQ 不可用时同步降级)
┌──────────────────────────────────────────────────────────────────┐
│  workers/ (多进程 WorkerPool / MQ Consumer)                       │
│  · Redis Pub/Sub 推送进度                                         │
│  · pytest 子进程执行                                             │
│  · 结果写 MySQL + Redis                                          │
└──────────────────────────────────────────────────────────────────┘

┌──────────────┬──────────────────┬──────────────────┐
│  MySQL × 3   │     Redis        │   RabbitMQ       │
│  数据持久化   │  任务状态缓存     │   异步任务队列    │
│  13 张表     │  24h TTL         │   test.execute   │
└──────────────┴──────────────────┴──────────────────┘
```

---

## 五、核心模块详解

### 5.1 LLM 层（`common/llm/`）

**llm_client.py** - 通义千问 DashScope HTTP 客户端：

- 支持模型：`qwen-plus`、`qwen-max`、`qwen-turbo`、`qwen-vl-plus`、`qwen-vl-max`、`qwen-coder-plus`
- 流式输出：`stream=True` 参数
- Token 管理：tiktoken 计数，自动截断（最大 8k tokens）
- Mock 模式：`LLM_MOCK_MODE=1` 环境变量，禁用 LLM 调用用于离线测试
- 并行批处理：`chat_batch()` 支持并发/串行切换
- 错误处理：欠费/无效Key/限流等特定错误码处理

**prompt_manager.py** - YAML 模板管理器（单例模式）：

- 加载 `app/prompts.yaml`
- 分类管理：`test_case_generation`、`iteration`、`document`、`qa`、`api_case`、`enhanced_test_case`
- 变体支持：positive（正向）/ negative（逆向）/ edge（边界）/ security（安全）

### 5.2 文档处理（`common/document/`）

统一入口 `UnifiedDocumentProcessor`：

1. **文档分类**（`document_classifier.py`）→ 识别类型：API_DESIGN / PRODUCT_DESIGN / TECHNICAL_SPEC / TEST_CASE / USER_GUIDE / REQUIREMENT
2. **类型路由** → 分发给对应处理器
3. **内容增强**（可选）→ LLM 补充缺失信息
4. **多级解析**（可选）→ 按层级深入提取
5. **输出** → `Document` dataclass（含 chunks 列表）

核心 `DocumentProcessor`：
- 切分策略：semantic（语义）/ fixed（固定长度）/ recursive（递归）/ hierarchical（层级）
- Token 计数：tiktoken（cl100k_base）
- 去重：内容相似度过滤
- 噪音清洗：HTML 标签、特殊字符

### 5.3 测试执行引擎（`common/test_executor/`）

**APITestRunner** 是执行核心：
- 串行模式：按顺序执行每个用例
- 并行模式：`concurrent.futures.ThreadPoolExecutor`，`max_workers` 可配置
- 变量替换：`{{var}}`（全局变量）、`${PREV.response.path}`（前序响应）、`{{timestamp}}`（时间戳）、`{{request_id}}`（UUID）、`{{random_int}}`（随机整数）
- 前后置脚本：`setup_script`（执行前）/ `post_script`（执行后，SQL 查询）
- DB 断言：`db_checks` 字段，14 种操作符

**pytest_generator.py** 将用例数据动态生成 `.py` 文件：
- 每个测试函数对应一个 `TestCaseExecutionData`
- Allure 装饰器：`@story` / `@severity` / `@feature`
- 失败自动重跑：`pytest-rerunfailures`
- 输出目录：`outputs/generated_tests/`

### 5.4 Worker 系统（`common/worker/` + `workers/`）

SQLite 任务队列（`task_poller.py`）：

```python
# 创建任务
task_id = create_task(task_type, payload, priority)
# 原子抢锁获取任务
task = poll_pending_task(worker_id)
# 更新状态
update_task_status(task_id, status, result, error)
```

任务分发（`task_processor.py`）按 `task_type` 分发：

| task_type | 处理函数 |
|---|---|
| `document_parse` | 文档解析 |
| `case_generate` | 用例生成 |
| `iteration_parse` | 迭代解析 |
| `page_case_generate` | 页面用例生成 |

WorkerPool：`cpu_count() * 2 + 1` 个子进程，每个子进程运行 `TestWorker` 线程。

### 5.5 数据库层（`common/db/`）

13 张 `crosstest_*` 表，SQLAlchemy ORM 统一管理。

连接池配置（`datacase/contect_db.py`）：
- 基础连接数：10
- 最大溢出：20
- 最大总连接：30
- 超时：30s
- 连接回收：1h
- 健康检查：`pool_pre_ping=True`
- 多数据源支持：通过 `db_config.json` 的 `db_key` 切换

---

## 六、数据流向

### 6.1 文档 → 测试用例生成

```
上传文档 (DOCX/PDF)
    ↓
blueprint_test_case_generate.py 接收
    ↓
UnifiedDocumentProcessor.classify()  [document/]
    ↓
UnifiedDocumentProcessor.process()   → 类型路由
    ↓
DocumentProcessor.clean() → chunk() → deduplicate()
    ↓
LLM: PromptManager + LLMClient.chat()
    ↓
用例 JSON → TestCase dataclass → 去重
    ↓
TestCaseMapper.insert() → MySQL (crosstest_test_case)
    ↓
返回用例列表（含 review_status = pending）
```

### 6.2 测试执行

```
选中用例（suite / plan / tag）
    ↓
blueprint_api_auto_test.py 接收
    ↓
APITestRunner.execute_batch() (parallel=True/False)
    ↓
ParameterResolver.resolve() → 变量替换
    ↓
requests.Session.request() → HTTP 调用
    ↓
AssertionExecutor.execute() → 10 种断言
    ↓
TestResult {passed, failed, duration, error}
    ↓
TestExecutionMapper.insert() → MySQL
    ↓
pytest_generator.py → 动态 .py → pytest → Allure 报告
```

### 6.3 异步任务处理

```
Blueprint → platform_service.service.task_service.create_task()
    ↓
MySQL (task_execution) + Redis (TTL 24h) 双写
    ↓
RabbitMQ publish (test.execute 队列) 或 SQLite 轮询降级
    ↓
WorkerPool (N 个子进程) → TaskProcessor.process()
    ↓
Redis Pub/Sub 推送实时进度
    ↓
结果写 MySQL → Redis 更新状态
```

---

## 七、API 端点总览

| Blueprint | URL 前缀 | 核心功能 |
|---|---|---|
| `test_case_gen_opt` | `/ai_service` | 文档 → 用例生成 |
| `ai_generate_opt` | `/ai_service` | AI 用例生成 |
| `doc_parser_opt` | `/ai_service` | AI 文档解析 |
| `enhanced_generate_opt` | `/ai_service` | 增强版用例生成 |
| `api_auto_test_bp` | `/api/auto_test` | API 自动化执行 |
| `test_exec_opt` | `/data_service` | 测试执行管理 |
| `test_case_import_opt` | `/data_service/testcase` | 外部格式导入 |
| `api_interface_xmind_bp` | `/api_interface_xmind` | XMind 格式导入 |
| `comparison_bp` | `/comparison` | 文档对比 |
| `page_test_case_bp` | `/page_test_case` | 页面级用例 |
| `data_factory_bp` | `/` | 测试数据工厂 |
| `data_generate_bp` | `/data_service` | 数据生成服务 |
| `api_config_opt` | `/data_service` | API 接口配置 |
| `db_config_opt` | `/data_service` | 数据库配置 |
| `env_config_opt` | `/data_service` | 环境配置 |
| `test_suite_bp` | `/api/test-suite` | 测试套件管理 |
| `assertions_bp` | `/` | 断言管理 |
| `tasks_bp` | `/` | 异步任务管理 |

---

## 八、运行方式

### 8.1 启动 Flask API 服务

```bash
python app/run.py
# 或：
python run.py
# 默认端口：127.0.0.1:8080
# 参数：--host, --port, --debug
```

### 8.2 启动 Worker 进程

```bash
# 方式一：直接启动
python workers/run_worker.py

# 方式二：带健康检查的启动脚本
python workers/start_workers.py
# 会依次检查 Redis / RabbitMQ / MySQL 连通性
# 按 Ctrl+C 优雅退出（SIGINT）
```

### 8.3 数据库迁移

```bash
alembic upgrade head
```

### 8.4 运行测试

```bash
# 冒烟测试
pytest tests/ -m smoke

# 回归测试
pytest tests/ -m regression

# 按优先级
pytest tests/ -m P0

# 并行执行
python scripts/run_smoke_tests.py --parallel --workers 4

# CI 模式
python scripts/run_ci_tests.py --marker regression --parallel --workers 4
```

---

## 九、当前存在的问题（启动前必须修复）

| 优先级 | 问题 | 影响 |
|---|---|---|
| **P0** | `app/__init__.py` 引用已删除的 `app/views/*` | **Flask 应用无法启动**，`ModuleNotFoundError` |
| **P1** | `common/config/__init__.py` 引用不存在的 `common/config/sql_config.json` | 配置加载失败 |
| **P2** | 根 `conftest.py` 调用未导入的 `send_email()` | pytest 运行时报 `NameError` |
| **P3** | `common/error_code/` 与 `utils/error_code/` 完全重复 | 代码重复，维护成本高 |
| **P4** | `common/rag/` 残留 24 个文件（已重构到 `common/document/`） | 目录结构混乱，需清理 |

---

*文档生成日期：2026-04-19*
