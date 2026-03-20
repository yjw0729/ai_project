# 测试 Agent 完整改造建议

## 📊 当前系统现状分析

### ✅ 已有功能

1. **配置管理**
   - ✅ 数据库配置管理（增删改查）
   - ✅ 环境配置管理（增删改查）
   - ✅ 接口配置管理（增删改查）

2. **测试案例管理**
   - ✅ 测试案例查询（支持多条件筛选）
   - ✅ 测试案例执行（基于 requests，支持并发）
   - ✅ 执行结果记录（test_execution 表）

3. **AI 能力**
   - ✅ 单接口测试案例自动生成（AI 生成）
   - ✅ 文档解析生成测试案例
   - ✅ **智能文档解析（多策略切片）** - 支持 semantic/recursive/hierarchical/hybrid/api_table

### 新增功能：智能文档解析

#### 接口信息

| 项目 | 内容 |
|------|------|
| **请求地址** | `POST /comparison/parse_with_strategy` |
| **请求格式** | multipart/form-data |

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 | 默认值 |
|--------|------|------|------|--------|
| `file` | File | 是 | 文档文件（支持 docx, pdf, txt, xlsx, xmind） | - |
| `strategy` | String | 否 | 切片策略：`semantic` / `recursive` / `hierarchical` / `hybrid` / `api_table` | `auto`（自动选择） |
| `doc_type` | String | 否 | 文档类型：`auto` / `api_doc` / `technical_spec` / `product_design` / `requirement` / `user_guide` / `test_case` | `auto` |
| `save_to_vector` | Boolean | 否 | 是否保存到向量库 | `false` |

#### 策略说明

| 策略 | 适用场景 | 特点 |
|------|----------|------|
| `semantic` | 语义完整性要求高的文档 | 按语义块分割，粒度粗 |
| `recursive` | 技术文档、规格文档 | 递归切分，粒度细 |
| `hierarchical` | API文档、结构化文档 | 保持层级结构 |
| `hybrid` | 混合文档 | 语义+递归结合，平衡最优 |
| `api_table` | API接口文档 | 专用API切片 |

#### 自动检测流程

```
上传文档 (不指定strategy和doc_type)
              ↓
     分类器自动检测文档类型
              ↓
    根据文档类型推荐最佳策略
              ↓
     使用推荐策略切片
```

**文档类型 → 推荐策略 映射**：

| 文档类型 | 推荐策略 |
|----------|----------|
| `api_doc` | hierarchical |
| `technical_spec` | recursive |
| `product_design` | hybrid |
| `requirement` | semantic |
| `user_guide` | semantic |
| `test_case` | semantic |

#### 响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "doc_id": "xxx-xxx-xxx",
    "filename": "基于SCA的用户授权服务.docx",
    "doc_type": "technical_spec",
    "strategy": "recursive",
    "original_length": 27093,
    "chunks_count": 47,
    "chunks": [
      {
        "chunk_id": 0,
        "title": "概述",
        "content": "文档内容...",
        "type": "recursive"
      }
    ]
  }
}
```

#### 使用示例

```bash
# 自动检测（推荐）
curl -X POST "http://localhost:5000/comparison/parse_with_strategy" \
  -F "file=@/path/to/document.docx"

# 指定策略
curl -X POST "http://localhost:5000/comparison/parse_with_strategy" \
  -F "file=@/path/to/document.docx" \
  -F "strategy=hybrid"

# 保存到向量库
curl -X POST "http://localhost:5000/comparison/parse_with_strategy" \
  -F "file=@/path/to/document.docx" \
  -F "save_to_vector=true"
```

---

4. **基础能力**
   - ✅ 动态变量替换（目前仅支持 `{{outTradeNo}}`）
   - ✅ 请求头合并（环境级 + 接口级 + 案例级）
   - ✅ 超时和重试配置

### ❌ 缺失功能

1. **流程测试（多接口串联）**
   - ❌ 场景/流程定义（多个接口按顺序执行）
   - ❌ 接口间数据传递（提取响应数据作为下个接口的入参）
   - ❌ 流程级断言和验证

2. **场景测试案例生成**
   - ❌ 基于业务流程自动生成场景测试案例
   - ❌ 多接口组合场景生成

3. **pytest + allure 集成**
   - ❌ pytest 测试框架集成
   - ❌ allure 报告生成
   - ❌ 测试结果持久化到 allure

4. **断言和验证**
   - ❌ 响应断言（状态码、字段值、JSON Schema）
   - ❌ 数据库断言（执行后验证数据库状态）
   - ❌ 业务规则验证

5. **数据管理**
   - ❌ 测试数据池管理
   - ❌ 数据驱动测试
   - ❌ 测试数据清理和恢复

---

## 🎯 核心功能需求

### 1. 单接口测试 ✅（已有基础，需增强）

**当前状态**：已有基础执行能力，但缺少：
- 完整的断言机制
- pytest 集成
- allure 报告

**需要增强**：
- 响应断言（状态码、JSON 字段、正则匹配）
- 数据库断言（可选）
- pytest fixture 封装
- allure 步骤记录

### 2. 流程测试 ❌（需要新增）

**核心能力**：
- 场景定义（多个接口按顺序执行）
- 数据提取和传递（从响应中提取数据，传递给下一个接口）
- 流程级断言（整个流程的最终结果验证）
- 条件分支（根据前一个接口的结果决定执行哪个接口）
- 循环执行（支持接口循环调用）

**数据结构**：
```json
{
  "name": "用户注册并登录流程",
  "description": "先注册用户，再使用注册的用户登录",
  "steps": [
    {
      "step_number": 1,
      "api_config_id": 1,
      "description": "注册用户",
      "extract": {
        "userId": "$.data.userId",
        "token": "$.data.token"
      }
    },
    {
      "step_number": 2,
      "api_config_id": 2,
      "description": "使用注册的用户登录",
      "dependencies": {
        "userId": "{{step1.userId}}",
        "token": "{{step1.token}}"
      }
    }
  ]
}
```

### 3. 自动生成接口测试案例 ✅（已有，需优化）

**当前状态**：已有 AI 生成能力

**需要优化**：
- 生成更全面的边界值测试案例
- 生成异常场景测试案例
- 生成性能测试案例（可选）

### 4. 自动生成场景测试案例 ❌（需要新增）

**核心能力**：
- 基于业务流程文档生成场景测试案例
- 识别接口间的依赖关系
- 自动生成数据传递逻辑
- 生成流程级断言

---

## 🏗️ 技术架构建议

### 1. 目录结构建议

```
pytest_sxp/
├── api/                          # Flask API 接口（已有）
├── common/                       # 公共模块（已有）
│   ├── db_entity/               # 数据库实体（已有）
│   ├── db_mapper/               # 数据访问层（已有）
│   └── process_function/        # 业务逻辑（已有）
├── core/                        # 🆕 核心测试引擎
│   ├── __init__.py
│   ├── test_engine.py           # 测试执行引擎
│   ├── assertion.py              # 断言引擎
│   ├── variable_extractor.py    # 变量提取器
│   └── flow_executor.py         # 流程执行器
├── pytest_plugin/               # 🆕 pytest 插件
│   ├── __init__.py
│   ├── fixtures.py              # pytest fixtures
│   ├── conftest.py              # pytest 配置
│   └── allure_integration.py    # allure 集成
├── generators/                   # 🆕 生成器模块
│   ├── __init__.py
│   ├── scenario_generator.py    # 场景测试案例生成器
│   └── flow_generator.py        # 流程测试案例生成器
├── tests/                        # 🆕 pytest 测试用例目录
│   ├── __init__.py
│   ├── test_single_api/         # 单接口测试
│   ├── test_flows/              # 流程测试
│   └── conftest.py              # pytest 配置
└── reports/                     # allure 报告目录（已有）
```

### 2. 核心模块设计

#### 2.1 测试执行引擎 (`core/test_engine.py`)

**职责**：
- 统一封装 requests 调用
- 处理动态变量替换
- 处理请求头合并
- 记录执行日志
- 集成 allure 步骤记录

**接口设计**：
```python
class TestEngine:
    def execute_api(
        self,
        api_config: Dict,
        env_config: Dict,
        test_data: Dict,
        extractors: List[Dict] = None
    ) -> TestResult:
        """
        执行单个接口测试
        
        :param api_config: 接口配置
        :param env_config: 环境配置
        :param test_data: 测试数据（包含 query/body/headers）
        :param extractors: 数据提取器列表 [{"name": "userId", "path": "$.data.userId"}]
        :return: TestResult 对象
        """
        pass
```

#### 2.2 断言引擎 (`core/assertion.py`)

**职责**：
- 响应断言（状态码、JSON 字段、正则）
- 数据库断言（可选）
- 业务规则验证

**接口设计**：
```python
class AssertionEngine:
    def assert_response(
        self,
        response: requests.Response,
        assertions: List[Dict]
    ) -> AssertionResult:
        """
        断言响应结果
        
        :param response: requests 响应对象
        :param assertions: 断言规则列表
            [
                {"type": "status_code", "expected": 200},
                {"type": "json_path", "path": "$.code", "expected": 0},
                {"type": "json_schema", "schema": {...}},
                {"type": "regex", "path": "$.message", "pattern": "成功"}
            ]
        :return: AssertionResult 对象
        """
        pass
```

#### 2.3 变量提取器 (`core/variable_extractor.py`)

**职责**：
- 从响应中提取数据（JSONPath、正则、XPath）
- 变量存储和传递
- 支持嵌套变量引用

**接口设计**：
```python
class VariableExtractor:
    def extract(
        self,
        response: requests.Response,
        extractors: List[Dict]
    ) -> Dict[str, Any]:
        """
        从响应中提取变量
        
        :param response: requests 响应对象
        :param extractors: 提取器列表
            [
                {"name": "userId", "type": "json_path", "path": "$.data.userId"},
                {"name": "token", "type": "json_path", "path": "$.data.token"},
                {"name": "orderNo", "type": "regex", "pattern": "ORDER\\d+"}
            ]
        :return: 提取的变量字典
        """
        pass
    
    def replace_variables(
        self,
        data: Any,
        variables: Dict[str, Any]
    ) -> Any:
        """
        替换数据中的变量占位符
        
        :param data: 需要替换的数据（dict/list/str）
        :param variables: 变量字典
        :return: 替换后的数据
        """
        pass
```

#### 2.4 流程执行器 (`core/flow_executor.py`)

**职责**：
- 执行多接口串联流程
- 管理步骤间的数据传递
- 支持条件分支和循环
- 流程级断言

**接口设计**：
```python
class FlowExecutor:
    def execute_flow(
        self,
        flow_config: Dict,
        env_config: Dict,
        initial_variables: Dict = None
    ) -> FlowResult:
        """
        执行流程测试
        
        :param flow_config: 流程配置
        :param env_config: 环境配置
        :param initial_variables: 初始变量
        :return: FlowResult 对象
        """
        pass
```

#### 2.5 pytest 集成 (`pytest_plugin/fixtures.py`)

**职责**：
- 提供 pytest fixtures（环境配置、接口配置、测试数据）
- 集成 allure 步骤记录
- 测试结果收集

**接口设计**：
```python
@pytest.fixture
def test_engine():
    """测试执行引擎 fixture"""
    return TestEngine()

@pytest.fixture
def env_config(env_id):
    """环境配置 fixture"""
    # 从数据库加载环境配置
    pass

@pytest.fixture
def api_config(api_config_id):
    """接口配置 fixture"""
    # 从数据库加载接口配置
    pass
```

---

## 📋 数据库设计补充

### 1. 流程测试表 (`test_flow`)

```sql
CREATE TABLE `crosstest_test_flow` (
  `id` INT PRIMARY KEY AUTO_INCREMENT,
  `name` VARCHAR(200) NOT NULL COMMENT '流程名称',
  `description` TEXT COMMENT '流程描述',
  `flow_config` JSON NOT NULL COMMENT '流程配置（步骤、数据传递、断言）',
  `module` VARCHAR(100) COMMENT '所属模块',
  `system` VARCHAR(100) COMMENT '所属系统',
  `priority` ENUM('P0', 'P1', 'P2', 'P3') DEFAULT 'P2',
  `status` ENUM('draft', 'active', 'inactive', 'deprecated') DEFAULT 'draft',
  `creator` VARCHAR(50) NOT NULL,
  `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) COMMENT='流程测试配置表';
```

### 2. 场景测试案例表 (`test_scenario`)

```sql
CREATE TABLE `crosstest_test_scenario` (
  `id` INT PRIMARY KEY AUTO_INCREMENT,
  `name` VARCHAR(200) NOT NULL COMMENT '场景名称',
  `description` TEXT COMMENT '场景描述',
  `scenario_type` ENUM('business', 'integration', 'e2e') DEFAULT 'business',
  `flow_ids` JSON COMMENT '关联的流程ID列表',
  `preconditions` TEXT COMMENT '前置条件',
  `expected_results` JSON COMMENT '期望结果',
  `module` VARCHAR(100),
  `system` VARCHAR(100),
  `status` ENUM('draft', 'active', 'inactive') DEFAULT 'draft',
  `creator` VARCHAR(50) NOT NULL,
  `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) COMMENT='场景测试案例表';
```

### 3. 测试执行结果表增强

**已有 `test_execution` 表，需要增强**：
- 支持流程测试结果记录
- 支持步骤级结果记录
- 支持 allure 报告路径存储

---

## 🔧 具体实现方案

### 阶段一：基础能力增强（优先级：高）

#### 1.1 断言引擎实现

**文件**：`core/assertion.py`

**功能**：
- 状态码断言
- JSON Path 断言
- JSON Schema 断言
- 正则匹配断言
- 数据库断言（可选）

**依赖**：
```bash
pip install jsonpath-ng jsonschema
```

#### 1.2 变量提取器实现

**文件**：`core/variable_extractor.py`

**功能**：
- JSONPath 提取
- 正则提取
- 变量替换（支持 `{{step1.userId}}` 格式）

**依赖**：
```bash
pip install jsonpath-ng
```

#### 1.3 pytest 集成

**文件**：
- `pytest_plugin/fixtures.py`
- `pytest_plugin/conftest.py`
- `pytest_plugin/allure_integration.py`

**功能**：
- 提供测试执行引擎 fixture
- 提供环境/接口配置 fixture
- 集成 allure 步骤记录
- 自动生成 pytest 测试用例

**依赖**：
```bash
pip install pytest pytest-allure-adaptor allure-pytest
```

### 阶段二：流程测试实现（优先级：高）

#### 2.1 流程执行器实现

**文件**：`core/flow_executor.py`

**功能**：
- 按顺序执行多个接口
- 数据提取和传递
- 条件分支（根据响应决定下一步）
- 循环执行（支持 for/while）

#### 2.2 流程测试 API

**文件**：`api/http_flow_test.py`

**功能**：
- 流程定义 CRUD
- 流程执行接口
- 流程执行结果查询

#### 2.3 流程测试 pytest 生成器

**文件**：`pytest_plugin/flow_test_generator.py`

**功能**：
- 根据流程配置自动生成 pytest 测试用例
- 集成 allure 报告

### 阶段三：场景测试案例生成（优先级：中）

#### 3.1 场景生成器实现

**文件**：`generators/scenario_generator.py`

**功能**：
- 基于业务流程文档生成场景测试案例
- 识别接口依赖关系
- 自动生成数据传递逻辑

#### 3.2 场景测试 API

**文件**：`api/http_scenario_test.py`

**功能**：
- 场景定义 CRUD
- 场景执行接口
- 场景执行结果查询

### 阶段四：优化和增强（优先级：低）

#### 4.1 测试数据管理

**功能**：
- 测试数据池管理
- 数据驱动测试
- 数据清理和恢复

#### 4.2 性能测试支持

**功能**：
- 接口性能测试
- 并发压力测试
- 性能报告生成

---

## 📦 依赖包清单

### 必需依赖

```txt
# 测试框架
pytest>=7.0.0
pytest-allure-adaptor>=2.9.0
allure-pytest>=2.9.0

# 断言和验证
jsonpath-ng>=1.5.3
jsonschema>=4.0.0

# 请求处理（已有）
requests>=2.28.0

# 数据库（已有）
SQLAlchemy>=1.4.0
pymysql>=1.0.0

# AI 能力（已有）
openai>=1.0.0
```

### 可选依赖

```txt
# 数据库断言
sqlalchemy-utils>=0.38.0

# 性能测试
locust>=2.0.0

# 数据生成
faker>=18.0.0
```

---

## 🎯 实施优先级建议

### 第一优先级（立即实施）

1. **断言引擎** - 单接口测试的基础能力
2. **变量提取器** - 流程测试的基础能力
3. **pytest 集成** - 测试框架集成
4. **allure 报告** - 测试报告生成

### 第二优先级（1-2周内）

1. **流程执行器** - 实现多接口串联
2. **流程测试 API** - 流程定义和执行接口
3. **流程测试 pytest 生成** - 自动生成 pytest 用例

### 第三优先级（2-4周内）

1. **场景测试案例生成** - AI 生成场景测试
2. **测试数据管理** - 数据池和数据驱动
3. **数据库断言** - 数据库验证能力

### 第四优先级（长期优化）

1. **性能测试支持** - 接口性能测试
2. **测试报告增强** - 更丰富的报告内容
3. **CI/CD 集成** - 持续集成支持

---

## 🔍 关键技术点

### 1. 变量提取和传递

**示例**：
```python
# 步骤1：注册用户，提取 userId
extract = {
    "userId": "$.data.userId",
    "token": "$.data.token"
}

# 步骤2：使用提取的变量
body = {
    "userId": "{{step1.userId}}",
    "token": "{{step1.token}}"
}
```

### 2. 条件分支

**示例**：
```json
{
  "step_number": 2,
  "condition": {
    "type": "json_path",
    "path": "$.code",
    "operator": "==",
    "value": 0
  },
  "if_true": {
    "api_config_id": 3
  },
  "if_false": {
    "api_config_id": 4
  }
}
```

### 3. allure 集成

**示例**：
```python
import allure

@allure.step("执行接口: {api_name}")
def execute_api(api_name, ...):
    with allure.step("发送请求"):
        response = requests.post(...)
    with allure.step("验证响应"):
        assert response.status_code == 200
    return response
```

### 4. pytest 动态生成测试用例

**示例**：
```python
def pytest_generate_tests(metafunc):
    if "test_case" in metafunc.fixturenames:
        # 从数据库加载测试用例
        cases = load_test_cases_from_db()
        metafunc.parametrize("test_case", cases)
```

---

## 📝 下一步行动

1. **创建核心模块目录结构**
2. **实现断言引擎**（`core/assertion.py`）
3. **实现变量提取器**（`core/variable_extractor.py`）
4. **实现 pytest 集成**（`pytest_plugin/`）
5. **实现流程执行器**（`core/flow_executor.py`）
6. **创建流程测试 API**（`api/http_flow_test.py`）
7. **实现场景生成器**（`generators/scenario_generator.py`）

---

## ❓ 需要确认的问题

1. **流程测试的复杂度**：
   - 是否需要支持复杂的条件分支？
   - 是否需要支持循环执行？
   - 是否需要支持并行执行多个接口？

2. **断言能力**：
   - 是否需要数据库断言？
   - 是否需要业务规则验证？
   - 是否需要性能断言？

3. **报告需求**：
   - allure 报告需要包含哪些信息？
   - 是否需要自定义报告模板？
   - 是否需要报告对比功能？

4. **数据管理**：
   - 测试数据是否需要支持数据池？
   - 是否需要支持数据驱动测试？
   - 是否需要自动清理测试数据？

---

## 📚 参考资源

- [pytest 官方文档](https://docs.pytest.org/)
- [allure 官方文档](https://docs.qameta.io/allure/)
- [JSONPath 语法](https://goessner.net/articles/JsonPath/)
- [JSON Schema 验证](https://json-schema.org/)

