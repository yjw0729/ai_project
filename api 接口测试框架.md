# API 自动化测试平台 - 开发实施文档

**版本：** v2.0
**日期：** 2026-03-23
**适用对象：** 后端开发工程师
**技术栈：** Python + pytest + Allure

---

## 一、项目概述

### 1.1 项目背景

构建一个企业级 API 自动化测试平台，提供测试用例管理、自动化执行、报告生成、流量回放、Mock 服务等核心功能。

### 1.2 功能范围

| 模块 | 功能 | 优先级 |
|------|------|--------|
| 测试用例管理 | 用例 CRUD、标签分类、元数据管理 | P0 |
| 测试套件管理 | 用例组合、批量执行、套件嵌套 | P0 |
| 参数化驱动 | 数据驱动测试、多数据源支持 | P0 |
| 执行控制 | 顺序/重复/大规模/分布式执行 | P0 |
| 断言生成 | 智能断言、响应验证 | P1 |
| 用例生成 | 基于 OpenAPI/文档自动生成用例 | P1 |
| 流量回放 | 录制生产流量并回放 | P1 |
| Mock 服务 | 模拟依赖接口返回 | P1 |
| 契约测试 | 验证接口与 Schema 一致性 | P2 |
| CI/CD 集成 | Jenkins/GitLab/GitHub 集成 | P1 |
| Allure 报告 | 可视化测试报告 | P0 |
| Fixtures 封装 | 通用逻辑封装 | P0 |

### 1.3 工程拆分规划

**第一阶段（单体架构）：** 所有模块在一个工程中

**第二阶段（拆分微服务）：**
```
api-test-platform/           # 主工程（测试执行核心）
├── test-core/               # 测试执行引擎（独立）
├── test-manager/            # 用例/套件管理（独立）
└── test-services/           # 辅助服务集群
    ├── mock-service/        # Mock 服务（独立部署）
    ├── traffic-service/     # 流量录制回放（独立部署）
    └── assertion-service/   # 断言生成服务（独立部署）
```

**建议：** 初期按模块划分目录，后期每个模块可独立为服务

---

## 二、现有数据库结构分析

### 2.1 核心数据表

根据现有代码，已实现以下数据表：

| 表名 | 实体类 | 说明 |
|------|--------|------|
| crosstest_test_case | TestCase | 测试用例表 |
| crosstest_test_suite | TestSuite | 测试套件表 |
| crosstest_test_suite_case | TestSuiteCase | 套件 - 用例关联表 |
| crosstest_test_plan | TestPlan | 测试计划表 |
| crosstest_api_config | ApiConfig | 接口配置表 |
| crosstest_environment_config | EnvironmentConfig | 环境配置表 |
| crosstest_database_config | DatabaseConfig | 数据库配置表 |
| crosstest_global_variable | GlobalVariable | 全局变量表 |

### 2.2 数据库设计评估

**优势：**
1. 已实现完整的用例 - 套件 - 计划三层管理模型
2. 支持乐观锁（version 字段），处理并发更新
3. 用例状态双维度设计（status + case_status），更灵活
4. 软删除支持（status='deprecated'）
5. 完整的审计字段（creator, created_time, updated_time）

**需补充的表：**
1. `crosstest_test_execution` - 测试执行记录表（已有 mapper 但需确认表结构）
2. `crosstest_traffic_record` - 流量录制记录表
3. `crosstest_mock_rule` - Mock 规则表
4. `crosstest_contract_spec` - 契约规范表（OpenAPI Schema 存储）
5. `crosstest_assertion_template` - 断言模板表

**设计冲突检查：**
- 现有用例表 `test_steps` 使用 JSON 存储，与设计中 YAML 存储方案不同
  - **建议：** 保留 JSON 存储，增加 YAML 导出/导入功能
- 现有用例有 `api_config_id` 关联，设计中未强调
  - **建议：** 保留此关联，强化用例与接口配置的绑定

---

## 三、可复用的现有逻辑

### 3.1 用例生成逻辑（已实现）

**位置：** `api/http_ai_generate_cases.py`

**核心功能：**
1. AI 生成测试用例接口（`/ai/generate_testcases`）
2. 文档解析生成用例（`/ai/parse_doc`、`/ai/generate_testcases_from_doc`）
3. 用例保存到数据库（`_save_cases_to_db`）
4. API 配置自动创建/关联（`_get_or_create_api_config`）

**可复用组件：**
```python
# 1. 用例转换器
def _case_to_entity(api_name, creator, case, api_config_id, module, system) -> TestCase

# 2. 文档解析器
from common.llm.doc_parser import parse_doc_file, constraints_from_fields, build_params_example

# 3. 大模型客户端
from common.llm.llm_client import OpenAILLMClient, LLMClient
```

**复用建议：**
- 契约测试模块的用例生成可直接复用 `generate_api_test_cases()` 函数
- 文档解析逻辑可直接使用，无需重新开发

### 3.2 数据库访问层（已实现）

**位置：** `common/db_mapper/`

**核心 Mapper：**
```python
from common.db_mapper.test_case_mapper import TestCaseMapper
from common.db_mapper.test_suite_mapper import TestSuiteMapper
from common.db_mapper.test_suite_case_mapper import TestSuiteCaseMapper
from common.db_mapper.test_plan_mapper import TestPlanMapper
from common.db_mapper.api_config_mapper import ApiConfigMapper
from common.db_mapper.environment_config_mapper import EnvironmentConfigMapper
```

**复用建议：**
- 测试管理模块直接使用现有 Mapper
- 新增的 Mapper 遵循相同模式（session_scope 上下文管理）

### 3.3 数据生成工具（已实现）

**位置：** `utils/auto_generate/`

**可用工具：**
- `generate_phone.py` - 生成手机号
- `generate_idcardno.py` - 生成身份证号
- `generate_cardNo.py` - 生成银行卡号
- `generate_address.py` - 生成地址
- `generate_customer.py` - 生成客户信息
- `generate_bussiness_license.py` - 生成营业执照

**复用建议：**
- 参数化驱动模块的数据生成器可直接引用这些工具
- 测试数据工厂模块可集成这些生成器

---

## 四、核心模块开发指南

### 4.1 核心执行引擎（core 模块）

**位置：** `core/runner.py`

**功能：** 测试执行调度器，统一封装 pytest 执行逻辑

**开发步骤：**

1. 创建 TestRunner 类，封装 pytest.main() 调用
2. 实现构建 pytest 参数的方法，支持：
   - 测试路径指定
   - 执行模式选择（顺序/重复/分布式）
   - 标签/优先级过滤
   - Allure 报告配置
3. 实现测试结果收集和处理逻辑
4. 提供 `run_suite()` 和 `run_cases()` 便捷方法

**实现要点：**
- 使用配置类管理执行参数
- 返回结构化的测试结果对象
- 支持同步和异步执行

**注意事项：**
- pytest.main() 返回的是退出码，需要额外处理收集结果
- 分布式执行时使用 `-n auto` 自动检测 CPU 核心数
- 重复执行需要安装 pytest-repeat 插件

**后续拆分：** 此模块是核心引擎，建议保留在主工程或独立为 `test-core` 服务

---

### 4.2 测试用例管理（与现有代码整合）

**现有实现：**
- 实体类：`common/db_enitiy/test_case.py`
- Mapper 类：`common/db_mapper/test_case_mapper.py`

**开发步骤：**

1. **直接复用现有 TestCase 实体**，字段已满足需求：
   - `case_id` - 业务用例编号（TEST_CASE_000000001 格式）
   - `name` - 用例名称
   - `module` - 所属模块
   - `system` - 所属系统（新增字段）
   - `priority` - 优先级（P0-P3）
   - `test_steps` - 测试步骤（JSON 数组）
   - `expected_results` - 期望结果
   - `case_status` - 启用/停用
   - `last_execution_status` - 最近执行结果

2. **复用 TestCaseMapper 的核心方法**：
   ```python
   mapper.get_by_id(id)              # 根据 ID 获取
   mapper.search_cases(keyword, module, priority)  # 搜索用例
   mapper.get_by_module(module)      # 按模块获取
   mapper.bulk_update_status(ids, status)  # 批量更新状态
   mapper.export_cases_to_json()     # 导出
   mapper.import_cases_from_json()   # 导入
   mapper.duplicate_case(id, new_name)  # 复制用例
   ```

3. **新增功能开发**：
   - 用例版本对比（基于 version 字段）
   - 用例评审流程（已有 review_status 字段）
   - 用例执行历史记录（关联 execution 表）

**注意事项：**
- 更新操作需处理乐观锁（`update_with_version_check` 方法）
- 用例删除使用软删除（status='deprecated'）

---

### 4.3 测试套件管理（与现有代码整合）

**现有实现：**
- 实体类：`common/db_enitiy/test_suite.py`
- Mapper 类：`common/db_mapper/test_suite_mapper.py`
- 关联表：`common/db_enitiy/test_suite_case.py`

**开发步骤：**

1. **直接复用现有 TestSuite 实体**：
   - `suite_type` - 套件类型（smoke/regression/function/performance/custom）
   - `module` - 所属模块
   - `tags` - 标签数组（JSON）
   - `config` - 套件配置（JSON）

2. **复用 TestSuiteCase 关联表**：
   - `suite_id` - 套件 ID
   - `case_id` - 用例 ID
   - `execution_order` - 执行顺序
   - `config` - 用例级配置（启用/禁用、超时等）

3. **复用 TestSuiteMapper 的核心方法**：
   ```python
   mapper.get_by_id(id)                 # 获取套件
   mapper.get_cases_by_suite(suite_id)  # 获取套件中的用例
   mapper.bulk_add_cases_to_suite()     # 批量添加用例
   mapper.reorder_suite_cases()         # 重新排序
   mapper.export_suites_to_json()       # 导出
   ```

**套件类型模板（已实现）：**
```python
TestSuite.create_smoke_suite()       # 冒烟测试套件
TestSuite.create_regression_suite()  # 回归测试套件
TestSuite.create_function_suite()    # 功能测试套件
TestSuite.create_performance_suite() # 性能测试套件
```

---

### 4.4 测试计划管理（与现有代码整合）

**现有实现：**
- 实体类：`common/db_enitiy/test_plan.py`
- Mapper 类：`common/db_mapper/test_plan_mapper.py`

**开发步骤：**

1. **直接复用现有 TestPlan 实体**：
   - `plan_type` - 计划类型（manual/scheduled/ci_cd）
   - `suites` - 套件 ID 数组（JSON）
   - `schedule_config` - 调度配置（定时任务）
   - `status` - 执行状态

2. **计划类型说明**：
   | 类型 | 说明 | 使用场景 |
   |------|------|----------|
   | manual | 手动执行 | 临时测试、探索性测试 |
   | scheduled | 定时执行 | 每日构建、夜间回归 |
   | ci_cd | CI/CD 集成 | 流水线触发 |

3. **复用 TestPlanMapper 的核心方法**：
   ```python
   mapper.create_plan()             # 创建计划
   mapper.start_plan_execution()    # 开始执行
   mapper.complete_plan_execution() # 完成执行
   mapper.get_plan_progress()       # 获取进度
   ```

**注意事项：**
- 定时执行需要额外的调度服务（如 APScheduler）
- CI/CD 集成需要 Webhook 支持

---

### 4.5 参数化驱动（新增模块）

**位置：** `parametrize/driver.py`

**功能：** 数据驱动测试，支持多种数据源

**开发步骤：**

1. **集成现有数据生成工具**：
   ```python
   from utils.auto_generate.generate_phone import generate_phone
   from utils.auto_generate.generate_idcardno import generate_idcardno
   from utils.auto_generate.generate_address import generate_address
   ```

2. **创建参数化装饰器**：
   ```python
   # data/params/login_data.yaml
   # 使用 CSV/YAML/JSON 存储测试数据
   - description: 正常登录
     username: testuser
     password: Test123456
     expected_code: 200
   ```

3. **实现变量替换**：
   - 支持 `{{var_name}}` 语法
   - 从 environment_config 读取环境变量
   - 从 global_variable 读取全局变量

**实现要点：**
- 装饰器返回 pytest.mark.parametrize
- 数据加载支持编码自动识别（UTF-8/GBK）

---

### 4.6 断言模块（与 AI 生成整合）

**位置：** `assertion/auto_generator.py`

**功能：** 断言自动生成和执行

**与现有代码整合：**

1. **复用 AI 用例生成中的断言逻辑**：
   - `http_ai_generate_cases.py` 中已有用例断言生成
   - 生成的 `expected_results` 字段存储断言列表

2. **断言类型定义**：
   ```python
   # 现有用例中的断言格式
   expected_results = [
       {"type": "status_code", "expected": 200},
       {"type": "json_path", "path": "$.code", "expected": 0},
       {"type": "contains", "expected": "success"}
   ]
   ```

3. **新增断言执行器**：
   ```python
   from assertion.validators import (
       StatusCodeValidator,
       JsonPathValidator,
       ContainsValidator,
       SchemaValidator
   )
   ```

---

### 4.7 契约测试模块（复用 AI 生成逻辑）

**位置：** `contract_testing/openapi_validator.py`

**功能：** 验证 API 响应符合 OpenAPI 规范

**与现有代码整合：**

1. **复用文档解析逻辑**：
   ```python
   # 现有代码位置：common/llm/doc_parser.py
   from common.llm.doc_parser import parse_doc_file

   # 解析 OpenAPI/Swagger 文档
   spec_data = parse_doc_file("openapi.yaml")
   ```

2. **复用 AI 用例生成**：
   ```python
   # 现有代码位置：common/llm/ai_case_generator.py
   from common.llm.ai_case_generator import generate_api_test_cases

   # 基于 OpenAPI 生成冒烟测试用例
   cases = generate_api_test_cases(
       api_name="接口名称",
       http_method="POST",
       path="/api/path",
       params_example={"param1": "value1"}
   )
   ```

3. **新增 Schema 验证器**：
   ```python
   import jsonschema

   def validate_response_against_schema(response_body, schema):
       """验证响应是否符合 Schema"""
       jsonschema.validate(response_body, schema)
   ```

**实现要点：**
- OpenAPI 文档解析可复用 `doc_parser.py`
- 用例生成可复用 `ai_case_generator.py`
- 需要新增的是 Schema 验证逻辑

---

### 4.8 流量回放模块（新增）

**位置：** `traffic_replay/recorder.py` 和 `traffic_replay/player.py`

**功能：** 录制生产流量并在测试环境回放

**开发步骤：**

1. **流量录制器**：
   - 集成 mitmproxy 拦截 HTTP 流量
   - 保存到 `traffic_record` 表
   - 支持过滤规则（按域名、路径等）

2. **流量转换器**：
   - 清洗敏感数据（token、密码等）
   - 转换为测试用例格式
   - 关联到现有 `test_case` 表

3. **流量回放器**：
   - 加载录制的流量数据
   - 发送请求到测试环境
   - 对比响应差异

**数据表设计（需新增）：**
```sql
CREATE TABLE crosstest_traffic_record (
    id INT PRIMARY KEY AUTOINCREMENT,
    request_method VARCHAR(10),
    request_url TEXT,
    request_headers JSON,
    request_body TEXT,
    response_status INT,
    response_headers JSON,
    response_body TEXT,
    recorded_time DATETIME,
    tags JSON
);
```

---

### 4.9 Mock 服务模块（新增）

**位置：** `mock_service/server.py`

**功能：** 模拟依赖接口，支持请求匹配和动态响应

**开发步骤：**

1. **定义 MockRule 实体**：
   ```python
   @dataclass
   class MockRule:
       id: str
       method: str
       url_pattern: str      # 支持正则
       response_status: int
       response_body: Any
       priority: int
   ```

2. **实现 Mock 服务器**：
   - 规则注册和管理
   - 请求匹配（支持正则 URL）
   - 响应生成（支持延迟模拟）

3. **集成 pytest fixtures**：
   ```python
   @pytest.fixture
   def mock_server():
       server = MockServer()
       yield server
       server.clear()
   ```

**数据表设计（需新增）：**
```sql
CREATE TABLE crosstest_mock_rule (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(200),
    method VARCHAR(10),
    url_pattern VARCHAR(500),
    response_status INT,
    response_body TEXT,
    priority INT DEFAULT 0,
    call_count INT DEFAULT 0
);
```

---

### 4.10 pytest Fixtures 封装（与现有代码整合）

**现有实现：**
- `common/fixtures/common/begin_method.py` - 前置方法
- `conftest.py` - 全局 fixtures

**开发步骤：**

1. **整理现有 fixtures**：
   ```python
   # 从 conftest.py 和 fixtures 目录提取
   - api_client        # API 客户端
   - db_session        # 数据库会话
   - test_user         # 测试用户数据
   ```

2. **新增 fixtures**：
   ```python
   # fixtures/auth.py
   @pytest.fixture
   def auth_token(api_client, config) -> str:
       """获取认证 Token"""
       response = api_client.post("/api/v1/login", json=config["auth"])
       return response.json()["token"]

   # fixtures/cleanup.py
   @pytest.fixture
   def cleanup_actions():
       """清理动作管理器"""
       actions = []
       yield actions
       for action in reversed(actions):
           action()
   ```

3. **分类组织 fixtures**：
   ```
   fixtures/
   ├── api_client.py    # API 客户端相关
   ├── auth.py          # 认证相关
   ├── database.py      # 数据库相关
   ├── cleanup.py       # 清理相关
   └── mock.py          # Mock 相关
   ```

---

## 五、CI/CD 集成说明

### 5.1 哪些用例在 CI/CD 流程中执行

**测试计划中的 ci_cd 类型计划：**

根据 `TestPlan` 实体的 `plan_type` 字段，测试计划分为三类：

```python
class PlanType(enum.Enum):
    MANUAL = "manual"    # 手动执行 - 不在 CI/CD 中
    SCHEDULED = "scheduled"  # 定时执行 - 可选
    CI_CD = "ci_cd"      # CI/CD 集成 - 在流水线中执行
```

**用例筛选规则：**

1. **通过套件关联**：
   - CI/CD 计划关联特定套件（`suites` 字段）
   - 套件关联特定用例（通过 `test_suite_case` 表）
   - 形成：CI/CD 计划 → 套件 → 用例 的关联链

2. **通过标签筛选**：
   ```python
   # 执行带有 smoke 标签的用例
   mapper.get_cases_with_tags(["smoke", "ci"])
   ```

3. **通过优先级筛选**：
   ```python
   # 执行 P0 优先级用例（冒烟测试）
   mapper.get_by_priority("P0")
   ```

### 5.2 CI/CD 配置示例

**Jenkins 配置：**
```groovy
// Jenkinsfile
stage('API Tests') {
    steps {
        sh '''
            # 执行标记为 ci_cd 的测试计划
            python -m pytest tests/ \\
                -m "ci_cd" \\
                --alluredir=allure-results \\
                -n auto
        '''
    }
}
```

**GitLab CI 配置：**
```yaml
# .gitlab-ci.yml
api_tests:
  stage: test
  script:
    - pytest tests/ -m "smoke or regression" --alluredir=allure-results
  artifacts:
    paths:
      - allure-results/
```

**GitHub Actions 配置：**
```yaml
# .github/workflows/api-tests.yml
- name: Run API tests
  run: |
    pytest tests/ -m "ci_cd" --alluredir=allure-results
```

### 5.3 CI/CD 流程说明

```
┌─────────────────────────────────────────────────────────────────┐
│  CI/CD Pipeline                                                  │
├─────────────────────────────────────────────────────────────────┤
│  1. Checkout 代码                                                │
│  2. 安装依赖 (pip install -r requirements.txt)                   │
│  3. 执行测试计划 (TestPlan.plan_type = 'ci_cd')                  │
│     ↓                                                            │
│     - 获取 ci_cd 类型的计划                                       │
│     - 获取计划关联的套件                                         │
│     - 获取套件关联的用例                                         │
│     - 执行 pytest                                                │
│  4. 生成 Allure 报告                                              │
│  5. 上传报告/发送通知                                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 六、开发流程建议

### 6.1 开发顺序

**第一阶段（基础框架）：** 1-2 周
1. 环境检查和依赖安装
2. 整理现有 fixtures 和 conftest
3. 核心执行引擎（runner）封装
4. Allure 报告集成

**第二阶段（与现有代码整合）：** 2-3 周
1. 测试用例管理（复用现有 TestCase 和 Mapper）
2. 测试套件管理（复用现有 TestSuite 和 Mapper）
3. 测试计划管理（复用现有 TestPlan 和 Mapper）
4. 参数化驱动（集成现有数据生成工具）

**第三阶段（增强功能）：** 2-3 周
1. Mock 服务
2. 流量回放
3. 断言模块（复用 AI 生成逻辑）
4. 契约测试（复用文档解析和用例生成）

**第四阶段（集成部署）：** 1 周
1. CI/CD 集成配置
2. 文档完善
3. 测试验证

### 6.2 代码规范

- 遵循 PEP 8 编码规范
- 使用 type hints 进行类型标注
- 函数和类必须有 docstring
- 单元测试覆盖率 >= 80%

### 6.3 版本控制

- 使用语义化版本（MAJOR.MINOR.PATCH）
- 特性分支开发，PR 合并
- 提交信息遵循约定式提交

---

## 七、测试验证

### 7.1 自测要求

每个模块开发完成后需要：
1. 编写单元测试（`tests/unit/`）
2. 编写集成测试（`tests/integration/`）
3. 编写端到端测试（`tests/e2e/`）

### 7.2 验收标准

| 模块 | 验收标准 |
|------|----------|
| 执行引擎 | 支持顺序/重复/分布式执行 |
| 用例管理 | 复用现有 TestCase，支持 CRUD |
| 套件管理 | 复用现有 TestSuite，支持套件嵌套 |
| 计划管理 | 复用现有 TestPlan，支持三种类型 |
| 参数化 | 支持 YAML/JSON/CSV 数据源 |
| 断言 | 支持 5 种以上断言类型 |
| Mock | 支持 URL 正则匹配 |
| 流量回放 | 能录制并回放简单流量 |
| Fixtures | 提供 10+ 个常用 fixtures |

### 7.3 性能要求

- 单用例执行时间 < 100ms（不含网络）
- 百例并发执行时间 < 30s
- 内存占用 < 500MB

---

## 八、常见问题

### Q1: pytest-xdist 分布式执行失败？

**A:** 确保：
- 测试用例之间无依赖
- 无共享状态或竞争条件
- 使用正确的 pytest 参数（`-n auto`）

### Q2: Allure 报告不显示中文？

**A:** 确保：
- 文件编码为 UTF-8
- 系统安装了中文字体
- Allure 版本支持中文

### Q3: Mock 规则不匹配？

**A:** 检查：
- URL 正则表达式是否正确
- 请求方法是否匹配
- 优先级设置是否合理

### Q4: 如何复用现有的 AI 用例生成逻辑？

**A:** 直接导入现有函数：
```python
from api.http_ai_generate_cases import (
    _save_cases_to_db,
    _get_or_create_api_config,
    _case_to_entity
)
from common.llm.ai_case_generator import generate_api_test_cases
```

### Q5: CI/CD 中如何指定执行的用例？

**A:** 三种方式：
1. 创建 `ci_cd` 类型的测试计划，关联特定套件
2. 使用 pytest 标记：`-m "smoke"`
3. 指定测试文件：`pytest tests/cases/smoke/`

---

## 九、附录

### 9.1 配置文件模板

**config/test_config.yaml**
```yaml
api:
  base_url: http://localhost:8000
  timeout: 30

auth:
  username: admin
  password: admin123

database:
  host: localhost
  port: 5432
  name: test_db
  user: test
  password: test123

execution:
  default_workers: auto
  default_repeat: 1
  timeout: 300
```

### 9.2 依赖清单

**requirements.txt**
```
# 核心
pytest>=7.0.0
pytest-xdist>=3.0.0
pytest-repeat>=0.9.0
allure-pytest>=2.13.0

# HTTP
httpx>=0.24.0
requests>=2.28.0

# 数据
pydantic>=2.0.0
PyYAML>=6.0
jsonpath>=0.82
jsonschema>=4.0.0

# Mock
responses>=0.23.0
pytest-mock>=3.10.0

# 契约
openapi-spec-validator>=0.5.0
schemathesis>=3.0.0

# 工具
python-dotenv>=1.0.0
tenacity>=8.0.0
```

### 9.3 pytest 配置

**pytest.ini**
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

addopts =
    -v
    --alluredir=./allure-results
    --tb=short
    -s

markers =
    smoke: 冒烟测试
    regression: 回归测试
    ci_cd: CI/CD 集成
    P0: P0 优先级
    P1: P1 优先级
    P2: P2 优先级
    P3: P3 优先级

log_cli = true
log_cli_level = INFO
```

---

**文档结束**
