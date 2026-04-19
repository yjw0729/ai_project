# pytest_sxp 项目结构文档

> 本文档由代码分析自动生成，涵盖项目中每个 Python 文件和配置文件的功能说明。
> 扫描日期：2026-04-18

> **项目定位：** AI 驱动的自动化测试平台。基于 Python/Flask + 通义千问（DashScope）LLM，从技术文档（API 文档、需求文档、设计文档）自动生成测试用例，并执行接口测试。

---

## ⚠️ 发现的问题（启动前必须修复）

在扫描过程中发现了多个阻断性问题，修复优先级如下：

| # | 问题 | 影响 | 优先级 |
|---|---|---|---|
| **P0** | `app/__init__.py` 引用已删除的 `platform_service.api/*` | **Flask 应用无法启动**，`create_app()` 抛出 `ModuleNotFoundError` | 必须修复 |
| **P1** | `common/config/__init__.py` 引用不存在的 `common/config/sql_config.json` | 配置加载失败，所有依赖此文件的模块崩溃 | 必须修复 |
| **P2** | `conftest.py` 调用未导入的 `send_email()` | 测试套件运行时报 `NameError` | 应修复 |
| **P3** | `common/error_code/` 与 `utils/error_code/` 内容完全相同 | 代码重复，维护成本高 | 建议修复 |
| **P4** | `common/rag/` 残留 24 个文件，与向量功能解耦后应迁移 | 目录结构混乱 | 建议整理 |

---

## 目录

1. [项目根目录](#1-项目根目录)
2. [app/ — Flask 应用](#2-app--flask-应用)
3. [common/ — 核心业务代码](#3-common--核心业务代码)
4. [platform_service/ — 平台服务层](#4-platform_service--平台服务层)
5. [workers/ — Worker 进程](#5-workers--worker-进程)
6. [utils/ — 工具函数](#6-utils--工具函数)
7. [tests/ — 测试套件](#7-tests--测试套件)
8. [core/ — Pytest 执行引擎](#8-core--pytest-执行引擎)
9. [fixtures/ — Pytest Fixtures](#9-fixtures--pytest-fixtures)
10. [migrations/ — 数据库迁移](#10-migrations--数据库迁移)
11. [scripts/ — 运维脚本](#11-scripts--运维脚本)
12. [其他目录](#12-其他目录)
13. [shared/ — 废弃兼容层](#13-shared--废弃兼容层)
14. [架构总览](#架构总览)

---

## 1. 项目根目录

| 文件 | 功能说明 |
|---|---|
| `requirements.txt` | Python 依赖清单：pytest, Flask, SQLAlchemy, pydantic, DashScope SDK, pika（RabbitMQ）, redis, pandas, alembic, pdfplumber, python-docx, openpyxl 等 |
| `pytest.ini` | Pytest 全局配置。markers：`smoke`（冒烟）、`regression`（回归）、`ci_cd`（CI/CD）、`P0`/`P1`/`P2`/`P3`（优先级）；指定 testpaths 为 `tests/`；配置日志格式和超时 |
| `alembic.ini` | Alembic 数据库迁移配置，迁移脚本位置为 `migrations/` |
| `run.py` | 生产环境入口。调用 `app.create_app()`，默认监听 `0.0.0.0:8080`，支持 `--host`/`--port`/`--debug` 参数 |
| `run_tests.py` | Worker 单元测试入口，调用 `unittest` 执行 `tests/unit/test_worker.py` |
| `conftest.py` | **根级 pytest hook**。`pytest_sessionfinish` 收集测试结果写入 `outputs/`；调用 `send_email()` 发送报告（**⚠️ 未导入 send_email，会报错**） |

---

## 2. app/ — Flask 应用

Flask 应用工厂，注册 16 个 Blueprint，负责 HTTP 请求接收和业务分发。

| 文件 | 功能说明 |
|---|---|
| `app/__init__.py` | **应用工厂** `create_app()`。设置 OpenBLAS/OMP 线程限制，注册 16 个 Blueprint。**⚠️ 第 68-70 行引用了已删除的 `platform_service.api/*`，会导致启动崩溃（P0 问题）** |
| `app/extensions.py` | `SafeTimedRotatingFileHandler` + Flask 日志配置，输出到 `logs/app_flask.log` |
| `app/run.py` | 备用启动脚本。启动前清理目标端口上残留的 Python 进程，避免 OpenBLAS 冲突 |
| `app/db_config.json` | 3 个 MySQL 数据源：`default1`（localhost:3308）、`opts`（22.50.6.9:3306）、`default`（22.50.6.73:3306） |
| `app/connectors/database_connector.py` | 数据库连接器（与 `common/rag/connectors/database_connector.py` 内容相同） |
| `app/config/rag/rag.json` | RAG 系统配置（top_k=5, chunk_size=1000, qwen-plus LLM）。**未被 Python 代码引用** |
| `app/config/rag/business_modules.json` | 业务模块注册表（跨境开户/交易、互联网开户/交易）。**未被 Python 代码引用** |
| `app/config/rag/embedding_models.json` | 按文档类型配置的 Embedding 模型映射。**未被 Python 代码引用** |

### app/views/ — Blueprint 层（16 个）

| 文件 | 功能说明 |
|---|---|
| `blueprint_data_generate.py` | 数据生成服务 |
| `blueprint_ai_generate_cases.py` | AI 用例生成 |
| `blueprint_ai_doc_parser.py` | AI 文档解析（提取 API 定义）。引用 `common.data_structures.review_data` → 需改为 `utils.data_structures.review_data` |
| `blueprint_database_config.py` | 数据库连接配置 CRUD |
| `blueprint_environment_config.py` | 环境配置 CRUD（dev/test/staging/prod） |
| `blueprint_api_config.py` | API 接口配置 CRUD |
| `blueprint_test_execution.py` | 测试执行管理 |
| `blueprint_test_case_generate.py` | **核心**：文档 → 接口识别 → LLM 生成 → 用例去重 → 存储全流程。支持同步/异步降级。引用 `common.rag.processors.*`、`common.rag.utils.*`（待整理） |
| `blueprint_document_comparison.py` | 文档对比。引用 `common.rag.processors.adaptive_processor`（待整理） |
| `blueprint_page_test_case.py` | 页面级测试用例生成（OCR）。引用 `common.rag.utils.xmind_generator`（待整理） |
| `blueprint_api_interface_xmind.py` | XMind 格式接口用例导入。引用 `common.rag.utils.api_doc_parser`（待整理） |
| `blueprint_api_auto_test.py` | **核心**：API 自动化测试执行，支持同步/异步两种模式 |
| `blueprint_enhanced_generate_cases.py` | 增强版用例生成（基于业务上下文） |
| `blueprint_test_case_import.py` | 测试用例外部格式导入 |
| `blueprint_data_factory.py` | 测试数据工厂（UUID/姓名/手机/身份证/银行卡） |
| `blueprint_assertions.py` | 断言管理 |
| `blueprint_tasks.py` | 异步任务管理 |

---

## 3. common/ — 核心业务代码

### 3.1 common/llm/ — LLM 调用层

| 文件 | 功能说明 |
|---|---|
| `common/llm/llm_client.py` | **通义千问 DashScope HTTP 客户端**。支持 qwen-vl-*/qwen-plus/qwen-max/qwen-coder，流式输出，Token 计数，自动截断，Mock 模式（`LLM_MOCK_MODE=1`） |
| `common/llm/doc_parser.py` | PDF/DOCX → 结构化 API 字段提取（字段名/类型/必填/描述），表格数据转换，正则提取 JSON 示例 |
| `common/llm/prompt_manager.py` | YAML Prompt 模板管理器（Singleton）。`get_test_case_prompt()`（含 positive/negative/edge 等变体），`get_iteration_prompt()`，`get_document_prompt()` 等 |
| `common/llm/ai_case_generator.py` | LLM 测试用例批量生成。调用 `prompt_manager` 加载模板，结合错误码库生成正向/逆向用例 |
| `common/llm/api_doc_analyzer.py` | OpenAPI/Swagger/流程图解析。`APIDocAnalyzer`，`FlowchartAnalyzer` |
| `common/llm/enhanced_case_generator.py` | 增强版用例生成，结合业务上下文（调用 `context_manager`） |

### 3.2 common/rag/ — 文档处理工具（⚠️ 待整理）

> 24 个文件。向量数据库已移除，但文档解析工具（XMind 生成器、API 文档解析器）仍在被 Blueprint 使用。
>
> **建议：** 将 `utils/` 和 `processors/` 中的工具迁移到 `common/document/`，然后删除整个 `common/rag/`。

| 文件 | 功能说明 | 被引用 |
|---|---|---|
| `common/rag/utils/api_doc_parser.py` | DOCX → API 字段提取（接口名/请求参数/响应参数） | `blueprint_api_interface_xmind.py` ✅ |
| `common/rag/utils/xmind_generator.py` | 测试用例 → XMind 思维导图导出（支持按页面维度组织） | `blueprint_test_case_generate.py`、`blueprint_page_test_case.py` ✅ |
| `common/rag/processors/api_auto_test_processor.py` | 上传文档 → 解析 OpenAPI/Swagger/Word/流程图，提取接口存入临时存储 | `blueprint_test_case_generate.py` ✅ |
| `common/rag/processors/adaptive_processor.py` | 自适应文档处理器（按类型选择处理策略） | `blueprint_document_comparison.py` ✅ |
| `common/rag/processors/document_classifier.py` | 自动识别文档类型（API/PRD/design/spec） | `blueprint_document_comparison.py` ✅ |
| `common/rag/processors/*.py`（其他 4 个） | 产品文档解析、多级解析、统一处理器等 | 未被引用 |
| `common/rag/core/*.py`（8 个文件） | 文档处理核心、词文档处理、数据收集 | 仅被 `processors/*.py` 内部引用 |
| `common/rag/connectors/*.py`（4 个文件） | 文件/数据库/Confluence 连接器 | 仅被 `core/*.py` 内部引用 |
| `common/rag/config.json` | 向量 DB 配置（dim=768, COSINE metric）。**未被代码引用** | — |
| `common/rag/collections.json` | Collection 定义（test_knowledge: 2 chunks, dim=768）。**未被代码引用** | — |

### 3.3 common/test_executor/ — 测试执行引擎

| 文件 | 功能说明 |
|---|---|
| `common/test_executor/__init__.py` | 导出 `APITestRunner`、`TestResult`、`ParameterResolver`、`FixtureManager`（**已移除 ReportGenerator**） |
| `common/test_executor/api_test_runner.py` | **核心运行器**。串行/并行执行，变量替换（`{{var}}`/`${PREV.data.id}`），前后置脚本，断言调用，变量提取 |
| `common/test_executor/parameter_resolver.py` | **变量替换引擎**。全局变量，`${PREV}` 前序响应访问，`{{request_id}}`/`{{business_order_no}}`/`{{random_int}}`/`{{timestamp}}` 特殊生成器，DB 查询注入 |
| `common/test_executor/fixture_manager.py` | Fixture 注册表：env_config、api_client、auth_token、test_data、db_connection，支持自定义 |
| `common/test_executor/pytest_generator.py` | **动态 .py 文件生成器**。将 `TestCaseExecutionData` 转为 pytest 文件，Allure 装饰器，失败重跑 |
| `common/test_executor/pytest_generator_suite.py` | 套件级 pytest 生成器 |
| `common/test_executor/db_check_runner.py` | `post_script` SQL + `db_checks` 字段断言编排 |
| `common/test_executor/db_query_executor.py` | 多数据源 SQL 执行器，变量替换，结果缓存 |
| `common/test_executor/db_field_validator.py` | 14 种操作符字段断言（equals/not_equals/contains/regex/between/in/is_null/length 等） |
| `common/test_executor/db_check_parser.py` | `post_script`/`db_checks` 配置解析器 |
| `common/test_executor/response_extract.py` | 响应字段提取 Fixture |
| `common/test_executor/test_case_executor.py` | DB 用例 → 执行数据 pipeline |
| `common/test_executor/expected_results.py` | `expected_results` 格式解析器 |

### 3.4 common/assertion/ — 断言核心（已从 `common/services/assertion/` 迁移）

| 文件 | 功能说明 |
|---|---|
| `common/assertion/__init__.py` | 统一导出所有验证器和生成器 |
| `common/assertion/validators.py` | 10 种验证器：`StatusCode`、`JsonPath`、`Contains`、`Schema`、`ResponseTime`、`Header`、`Regex`、`Length`、`Type`、`NotEmpty`。`AssertionExecutor` 批量执行，`AssertionResult` 返回 passed/expected/actual/message |
| `common/assertion/auto_generator.py` | `AssertionGenerator`：HTTP 响应 → 断言列表（自动生成 status_code/response_time/JSON path）；`SmartAssertionGenerator` 基于 AI 智能生成 |

### 3.5 common/services/ — 业务服务层

| 文件 | 功能说明 |
|---|---|
| `common/services/__init__.py` | 导出 `AssertionService`、`AssertionEngine`、`AssertionGenerator` |
| `common/services/assertion_engine.py` | **断言服务封装**。`AssertionService.validate()` 执行断言列表返回摘要。`AssertionEngine` + `VariableContext` + `AssertionEvaluator` |
| `common/services/case_generator.py` | `TestCase` dataclass + LLM 批量生成用例 |
| `common/services/data_factory.py` | `DataFactoryService`：UUID、中文姓名、邮箱、手机号、身份证号、银行卡号、地址、日期、枚举值 |
| `common/services/document_parser.py` | `DocumentParserService`：LLM 辅助提取接口、文档结构和业务规则 |

### 3.6 common/business_context/ — 业务上下文管理

| 文件 | 功能说明 |
|---|---|
| `common/business_context/context_manager.py` | "先清洗再存储"原则。从文本/文件/图片提取内容，LLM 清洗结构化（修正 OCR、补全缺失、提取实体/流程/规则），存储清洗后内容 |

### 3.7 common/mq/ — 消息队列协议

| 文件 | 功能说明 |
|---|---|
| `common/mq/__init__.py` | 统一导出 schemas、messages、trace 工具 |
| `common/mq/schemas.py` | Pydantic 模型：`TaskStatus`、`TaskType`、`TaskCreateRequest/Response`、`ExecuteTestRequest/Response`、`APIResponse` 等 |
| `common/mq/mq_messages.py` | `MQMessage` + `MQQueueConfig`。4 条队列：llm.generate、test.execute、rag.index、report.generate |
| `common/mq/trace.py` | `TraceContext`（trace_id/user_id/request_id）、`LogFormatter`、`setup_trace_logging()` |

### 3.8 common/worker/ — Worker 抽象层

| 文件 | 功能说明 |
|---|---|
| `common/worker/__init__.py` | Worker 包入口 |
| `common/worker/task_poller.py` | SQLite 任务轮询。`create_task()`、`claim_task()`（分布式抢锁）、`poll_pending()` |
| `common/worker/task_processor.py` | 按 task_type 分发到注册的处理函数 |
| `common/worker/test_worker.py` | 基于 Thread 的 TestWorker |
| `common/worker/worker_pool.py` | 基于 Process 的 WorkerPool。`get_optimal_worker_count()` = `cpu_count * 2 + 1` |

### 3.9 common/db_enitiy/ — SQLAlchemy ORM 实体（13 张表）

| 文件 | 对应表 | 说明 |
|---|---|---|
| `api_config.py` | `crosstest_api_config` | HttpMethod 枚举 |
| `test_case.py` | `crosstest_test_case` | TestCasePriority P0-P3 |
| `test_execution.py` | `crosstest_test_execution` | ExecutionStatus 枚举 |
| `test_suite.py` | `crosstest_test_suite` | — |
| `test_suite_case.py` | `crosstest_test_suite_case` | — |
| `test_plan.py` | `crosstest_test_plan` | — |
| `database_config.py` | `crosstest_database_config` | EnvType/DbType 枚举 |
| `environment_config.py` | `crosstest_environment_config` | base_url, headers JSON |
| `global_variable.py` | `crosstest_global_variable` | — |
| `review_record.py` | `crosstest_review_record` | 每个接口一行 |
| `review_summary.py` | `crosstest_review_summary` | 每个文档一行 |
| `task_execution.py` | `crosstest_task_execution` | — |
| `business_context.py` | `crosstest_business_context` | — |

### 3.10 common/db_mapper/ — 数据库 Mapper（13 个）

每个 Mapper 对应一张表，提供 CRUD 操作。统一引用 `common.datacase_function.contect_db` 的 SQLAlchemy 会话。

### 3.11 common/models/ — 共享数据模型

| 文件 | 功能说明 |
|---|---|
| `common/models/task.py` | `Task` dataclass + `TaskStatus`/`TaskType` 枚举 |
| `common/models/assertion.py` | `AssertionType`、`AssertionSource`、`AssertionField`、`AssertionTemplate`、`AssertionConfig`（SQLite CRUD）|
| `common/models/document.py` | `Document` dataclass + `DocumentType` 枚举 |
| `common/models/interface.py` | `Interface` dataclass + `InterfaceStatus`/`HttpMethod` 枚举 |
| `common/models/test_data.py` | `TestDataConfig` dataclass |

### 3.12 common/config/ — 统一配置加载

| 文件 | 功能说明 |
|---|---|
| `common/config/__init__.py` | **⚠️ P1 问题：** 调用 `load_config("sql_config.json")`，但 `common/config/sql_config.json` 文件不存在。应补充该文件或移除此引用。统一配置加载器（XML/YAML/SQL/JSON） |

---

## 4. platform_service/ — 平台服务层

> ⚠️ `app/__init__.py` 引用了已删除的 `platform_service.api/*`，需要先修复才能启动。

| 文件 | 功能说明 |
|---|---|
| `platform_service/__init__.py` | 主入口，`__all__ = []`（无实质导出） |
| `platform_service/service/__init__.py` | 导出 `TaskService`、`MQClient`、`MQConsumer`、`async_api_helpers` |
| `platform_service/service/task_service.py` | Redis + MySQL 双写任务管理。`create_task`（同时写 MySQL + Redis 24h TTL），`get_status`（优先 Redis → 降级 MySQL），`claim_task` 分布式抢锁 |
| `platform_service/service/mq_client.py` | RabbitMQ 单例发布客户端，自动重连。`MQConsumer` 基类供 Worker 继承 |
| `platform_service/service/rate_limiter.py` | **废弃存根（nop）**，无任何限流实现 |
| `platform_service/service/async_api_helpers.py` | TaskService + MQClient 懒加载封装，Flask Blueprint 专用 |

---

## 5. workers/ — Worker 进程

| 文件 | 功能说明 |
|---|---|
| `workers/run_worker.py` | CLI 入口（多进程）。`WorkerPool` 管理子进程 |
| `workers/start_workers.py` | 统一启动脚本。Redis/RabbitMQ/MySQL 健康检查 + SIGINT 优雅退出 |
| `workers/mq_consumer.py` | `TestWorker`：消费 `test.execute` 队列 → 执行 pytest → Redis Pub/Sub 推送进度 → 结果写 MySQL |

---

## 6. utils/ — 工具函数

> 6 个子包，26 个 Python 文件。

| 文件 | 功能说明 |
|---|---|
| `utils/auto_generate/` | **测试数据生成器**（12 个文件）。`generate_customer`（姓名/公司名/邮箱/地址）、`generate_phone`（手机号）、`generate_idcardno`（身份证）、`generate_cardNo`（银行卡）、`generate_address`（地址）、`generate_picture`（银行卡图片校验）、`generate_picture_temple`（身份证模板）、`generate_hkpicture`（港澳通行证）、`generate_bussiness_license`（营业执照）、`generate_requestId`（随机串）、`areas`（省市代码静态数据） |
| `utils/csv_function/read_date_from_csv.py` | `resd_data_from_csv(path)` — CSV 读取 |
| `utils/csv_function/write_data_to_csv.py` | `writr_data_to_csv(heads, data, path)` — CSV 写入 |
| `utils/csv_function/read_date_from_yaml.py` | `YamlTestCaseParser` — YAML 用例解析，支持 `{{request_id}}` 模板变量 |
| `utils/datacase_function/contect_db.py` | SQLAlchemy engine/session 工厂（按 db_key 缓存），`db_session` 上下文管理器，`test_connection()` 健康检查 |
| `utils/datacase_function/read_datebase.py` | `execute_query(sql, param)` — pymysql 简单封装 |
| `utils/data_structures/review_data.py` | `ReviewData` dataclass — 文档审核流程数据载体 |
| `utils/error_code/error_code_library.py` | 错误码库。`ErrorCodeLibrary` 从 JSON 加载，提供 `get_error_by_code()`、`get_assertion()`、`get_success_assertion()` |
| `utils/image_analysis/image_analyzer.py` | `ImageAnalyzer`：OCR 文字识别、流程图分析 |

**⚠️ 重复问题：** `common/error_code/error_code_library.py` 与 `utils/error_code/error_code_library.py` 内容完全相同（代码重复）。

---

## 7. tests/ — 项目自身测试套件

| 文件 | 功能说明 |
|---|---|
| `tests/conftest.py` | 全局 fixtures：`http_session`、`env_base_url`、`execution_config`；`_extract_fields_by_config()`；`pytest_sessionfinish` hook |
| `tests/test_assertion_engine.py` | 断言验证器单元测试（`StatusCode`、`JsonPath`、`Contains` 等 10 种） |
| `tests/test_generate_testcases_from_doc.py` | 文档生成用例 API 集成测试 |
| `tests/test_db_assertion.py` | 数据库断言集成测试 |
| `tests/unit/test_worker.py` | Worker 模块单元测试（Task、TaskPoller、WorkerPool、TaskProcessor） |

---

## 8. core/ — Pytest 执行引擎

| 文件 | 功能说明 |
|---|---|
| `core/runner.py` | `TestRunner` 类（645 行）：串行/重复/分布式执行，Allure 报告，`pytest` 子进程调用。**未被任何代码引用**，属于独立构建的执行引擎 |

---

## 9. fixtures/ — Pytest Fixtures

| 文件 | 功能说明 |
|---|---|
| `fixtures/conftest.py` | Fixture 聚合入口 |
| `fixtures/api_client.py` | HTTP 客户端 fixtures |
| `fixtures/database.py` | 数据库连接 fixtures |
| `fixtures/auth.py` | 认证 Token fixtures |
| `fixtures/cleanup.py` | 资源清理 fixtures |

---

## 10. migrations/ — 数据库迁移

| 文件 | 功能说明 |
|---|---|
| `migrations/env.py` | Alembic 环境配置，读取 `app/db_config.json` 的 `default` 数据源 |
| `migrations/versions/001_initial.py` | **初始迁移**：创建全部 13 张 `crosstest_*` 表 |
| `migrations/add_extract_fields.py` | ALTER TABLE：`crosstest_test_case` 新增 `extract_fields` JSON 列 |
| `migrations/add_missing_suite_case_columns.py` | ALTER TABLE：`crosstest_test_suite_case` 新增 12 个缺失列（幂等检查） |

---

## 11. scripts/ — 运维脚本

| 文件 | 功能说明 |
|---|---|
| `scripts/start_services.py` | 多服务启动脚本。Redis/RabbitMQ/MySQL 健康检查，`platform`（Flask 端口 5000）和 `workers` 启动 |
| `scripts/run_ci_tests.py` | CI 测试运行（`--marker`/`--parallel`/`--workers`） |
| `scripts/run_smoke_tests.py` | 冒烟测试运行（`--verbose`/`--parallel`/`--workers`） |
| `scripts/verify_phase1.py` | 阶段性验证脚本（**已过时，建议删除**） |

---

## 12. 其他目录

| 目录 | 文件 | 功能说明 |
|---|---|---|
| `db/` | `db/__init__.py` | SQLite 任务队列初始化 |
| `examples/` | `rag_api_demo.py`、`final_api_demo.py`、`list_demo_files.py` | API 示例脚本（独立使用） |
| `parametrize/` | `driver.py`、`test_driver.py` | 数据驱动测试框架（YAML/JSON/CSV 数据源） |
| `mock_service/` | `server.py` | MockServer：Flask 规则注册、动态响应 |
| `infrastructure/rabbitmq/` | `docker-compose.yml` | RabbitMQ Docker 配置（端口 5672/15672/15692，用户 admin/pytest_sxp_2026） |

---

## 13. shared/ — 废弃兼容层

> **已废弃**。所有功能已被 `common/mq/` 替代。仅 `scripts/verify_phase1.py` 引用了它（删除该脚本后可整体删除）。

| 文件 | 功能说明 |
|---|---|
| `shared/__init__.py` | 重导出 `common.mq` 所有内容 |
| `shared/common_proto/schemas.py` | 重导出 `common.mq.schemas` |
| `shared/common_proto/mq_messages.py` | 重导出 `common.mq.mq_messages` |
| `shared/common_proto/trace.py` | 重导出 `common.mq.trace` |
| `shared/llm_sdk/llm_client.py` | 重导出 `common.llm.llm_client` |
| `shared/setup.py` | pip 包定义（`pytest-sxp-shared`） |

---

## 架构总览

```
HTTP 请求（外部）
       │
       ▼
┌──────────────────────────────────────────┐
│  app/__init__.py (create_app)             │
│  ⚠️ P0: 引用已删除的 platform_service.api │
└──────────────┬─────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│  app/views/  (Flask Blueprints × 16)      │
│  ├── common.llm.* (LLM 调用)             │
│  ├── common.services.* (业务逻辑)        │
│  ├── common.db_mapper.* (DB CRUD)        │
│  ├── common.test_executor.* (测试执行)     │
│  ├── common.rag.processors/* (文档处理)  │
│  ├── common.assertion/* (断言)           │
│  ├── platform_service.service.* (异步)   │
│  └── utils.auto_generate/* (数据生成)     │
└──────────────┬─────────────────────────────┘
               │
               ▼ (MQ 不可用时降级同步)
┌──────────────────────────────────────────┐
│  workers/mq_consumer.py (TestWorker)      │
│  · 消费 test.execute 队列               │
│  · Redis Pub/Sub 推送进度                │
│  · pytest 执行生成测试                   │
│  · 结果写 MySQL + Redis                 │
└──────────────────────────────────────────┘

持久层：
  MySQL × 3  → crosstest_* 表（数据持久化）
  Redis      → 任务状态缓存（24h TTL）
  RabbitMQ   → 异步任务队列
  SQLite    → Worker 轮询队列
```

---

## 服务依赖矩阵

| 组件 | 依赖 | 默认地址 | 用途 |
|---|---|---|---|
| Flask API | MySQL | 22.50.6.9:3306 等 | 数据持久化 |
| Flask API（部分 Blueprint） | Redis + RabbitMQ | localhost:6379 / 5672 | 异步任务（可选，有降级） |
| Workers | Redis + RabbitMQ + MySQL | localhost:6379 / 5672 / 远程 | 任务消费、缓存、持久化 |
| 所有组件 | Tongyi LLM | dashscope.aliyuncs.com（公网） | AI 用例生成、文档解析 |

---

*文档生成日期：2026-04-18*
