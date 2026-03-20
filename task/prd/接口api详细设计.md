# 接口API自动化测试功能 - 详细设计文档

> 本文档描述AI测试平台的接口API自动化测试功能的详细设计。

---

## 一、功能概述

### 1.1 背景与目标

当前系统已实现：
- 从需求文档/产品文档生成测试用例（XMind格式）
- RAG知识库构建与检索
- 已有测试用例的手动执行

本次新增功能：
- **接口API自动化测试**：上传OpenAPI文档或接口说明文档 + 流程图，自动生成接口测试用例并直接插入数据库，一键执行

### 1.2 设计原则

| 原则 | 描述 |
|------|------|
| **非侵入式扩展** | 新功能独立模块，不影响现有功能 |
| **五层架构分离** | API层 → LLM层 → RAG层 → 执行层 → 数据层 |
| **向后兼容** | 保持现有数据库表结构不变 |
| **可插拔** | 各层模块可独立替换和扩展 |

---

## 二、系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                        API接口层 (Layer 1)                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ 上传文档API      │  │ 生成用例API      │  │ 执行测试API      │  │
│  │ /api/upload     │  │ /api/generate    │  │ /api/execute     │  │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘  │
└───────────┼─────────────────────┼─────────────────────┼────────────┘
            │                     │                     │
            ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        LLM智能层 (Layer 2)                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ OpenAPI解析      │  │ 测试用例生成     │  │ 流程图分析       │  │
│  │ (API文档处理)    │  │ (AI增强生成)     │  │ (多模态理解)     │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
            │                     │                     │
            ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        RAG向量层 (Layer 3)                           │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ 向量索引构建     │  │ 语义检索增强     │  │ 知识库管理       │  │
│  │ (ChromaDB)       │  │ (混合检索)        │  │ (文档分块)        │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
            │                     │                     │
            ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        测试执行层 (Layer 4)                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ pytest框架       │  │ 参数化测试       │  │ Fixtures管理     │  │
│  │                  │  │                  │  │                  │  │
│  │ ┌──────────────┐ │  │ ┌──────────────┐ │  │ ┌──────────────┐ │  │
│  │ │ 动态用例生成 │ │  │ │ 接口依赖链   │ │  │ │ 环境配置     │ │  │
│  │ └──────────────┘ │  │ └──────────────┘ │  │ └──────────────┘ │  │
│  │ ┌──────────────┐ │  │ ┌──────────────┐ │  │ ┌──────────────┐ │  │
│  │ │ 参数传递     │ │  │ │ 断言管理     │ │  │ │ 结果收集     │ │  │
│  │ └──────────────┘ │  │ └──────────────┘ │  │ └──────────────┘ │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
            │                     │                     │
            ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        数据层 (Layer 5)                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ 测试用例库       │  │ 测试套件库       │  │ 执行记录库       │  │
│  │ (test_case)      │  │ (test_suite)     │  │ (test_execution) │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ 接口配置库       │  │ 环境配置库       │  │ 全局变量库       │  │
│  │ (api_config)     │  │ (env_config)     │  │ (global_variable)│  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 新增模块与现有模块关系

```
现有模块                              新增模块
┌─────────────────────┐              ┌─────────────────────┐
│ http_test_case_     │ ──────────▶ │ http_api_auto_      │
│ generate.py         │              │ test.py             │
│ (生成XMind用例)     │              │ (API自动化测试)     │
└─────────────────────┘              └─────────────────────┘
           │                                   │
           ▼                                   ▼
┌─────────────────────┐              ┌─────────────────────┐
│ api_doc_processor   │              │ api_auto_test_      │
│ (API文档解析)       │ ◀─────────── │ processor.py        │
│                     │   复用/扩展   │ (API自动测试处理器) │
└─────────────────────┘              └─────────────────────┘
           │                                   │
           ▼                                   ▼
┌─────────────────────┐              ┌─────────────────────┐
│ ai_case_generator   │              │ api_test_executor   │
│ (AI用例生成)        │ ◀─────────── │ .py                 │
│                     │   复用/扩展   │ (API测试执行器)     │
└─────────────────────┘              └─────────────────────┘
           │                                   │
           ▼                                   ▼
┌─────────────────────┐              ┌─────────────────────┐
│ test_case_mapper    │              │ test_case_mapper    │
│ (数据库操作)        │ ──────────▶ │ (复用现有)          │
└─────────────────────┘              └─────────────────────┘
```

---

## 三、功能详细设计

### 3.1 核心流程

#### 3.1.1 完整业务流程

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              业务流程                                       │
└──────────────────────────────────────────────────────────────────────────────┘

  [开始]
     │
     ▼
┌─────────────┐
│ 上传文档    │ ───▶ 支持：OpenAPI文档(.json/yaml)、接口说明(.docx)、流程图(.png/.jpg)
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│  文档类型识别与解析                                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ OpenAPI解析器   │  │ Word文档解析器 │  │ 图片流程分析    │  │
│  │ (Swagger/YAML)  │  │ (python-docx)  │  │ (LLM多模态)    │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│  接口信息提取                                                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ 接口名称/路径   │  │ 请求/响应参数   │  │ 接口依赖关系   │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│  AI增强测试用例生成                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ 边界值分析     │  │ 等价类划分      │  │ 业务场景覆盖   │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ 正向用例       │  │ 异常用例        │  │ 关联接口用例   │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│  测试用例插入数据库                                              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 生成 test_case 表记录，设置 api_config_id 关联          │   │
│  │ 自动生成 case_id: TEST_CASE_XXXXXXXXX                   │   │
│  │ 状态设为 active，case_status 设为 enabled               │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│  一键执行测试                                                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ 参数替换        │  │ 接口调用        │  │ 断言验证       │  │
│  │ (变量插值)     │  │ (requests)      │  │ (响应校验)     │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ 接口依赖传递   │  │ 并发执行       │  │ 结果收集       │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│  执行结果报告                                                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ 成功/失败统计   │  │ 失败详情       │  │ 执行时间记录   │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
       │
       ▼
  [结束]
```

#### 3.1.2 新增接口API

| 接口 | 方法 | 路径 | 描述 |
|------|------|------|------|
| 上传API文档 | POST | `/api/auto_test/upload` | 上传OpenAPI或接口说明文档 |
| 生成测试用例 | POST | `/api/auto_test/generate` | 根据文档和流程图生成测试用例 |
| 批量执行测试 | POST | `/api/auto_test/execute` | 执行选定的测试用例 |
| 查询执行结果 | GET | `/api/auto_test/results/{execution_id}` | 获取执行结果详情 |
| 导出测试报告 | GET | `/api/auto_test/report/{execution_id}` | 导出Allure格式报告 |

### 3.2 数据结构设计

#### 3.2.1 测试用例格式（test_case表）

```python
# 新增用例的数据结构
test_case = {
    "name": "创建客户_必填参数正常",
    "description": "验证创建客户接口在必填参数正常时的响应",
    "module": "客户管理",           # 从接口文档提取
    "system": "普通收单系统",      # 从文档元数据提取
    "priority": "P1",              # AI智能判断
    "tags": ["正向", "必填", "客户管理"],
    
    "api_config_id": 123,          # 关联接口配置
    
    "test_steps": [
        {
            "step": 1,
            "action": "发送POST请求 /api/customer/create",
            "data": {
                "request": {
                    "method": "POST",
                    "path": "/api/customer/create",
                    "headers": {"Content-Type": "application/json"},
                    "body": {
                        "customerName": "测试客户",
                        "idCardNo": "320123199001011234"
                    }
                }
            }
        },
        {
            "step": 2,
            "action": "验证响应状态码为200",
            "expected": "status_code == 200"
        },
        {
            "step": 3,
            "action": "验证响应体包含customerId",
            "expected": "response.body.customerId is not None"
        }
    ],
    
    "expected_results": [
        "响应状态码为200",
        "响应时间小于500ms",
        "返回客户ID"
    ],
    
    "test_data": {
        "request": {...},           # 请求参数
        "response": {...},          # 期望响应
        "variables": {},            # 接口变量（用于参数传递）
        "dependencies": []          # 依赖接口列表
    },
    
    "variables": {
        "out_trade_no": "{{outTradeNo}}",  # 动态变量
        "customer_id": "${PREV_RESPONSE.customerId}"  # 前置接口变量
    },
    
    "setup_scripts": [],            # 前置脚本
    "teardown_scripts": [],        # 后置脚本
    
    "max_retry_times": 2,
    "timeout": 30,
    
    "status": "active",
    "case_status": "enabled",
    "last_execution_status": "not_run"
}
```

#### 3.2.2 测试套件格式（test_suite表）

```python
test_suite = {
    "name": "普通收单系统-客户管理模块",
    "description": "普通收单系统客户管理模块接口测试套件",
    "module": "客户管理",
    "system": "普通收单系统",
    "test_case_ids": [1, 2, 3, 4, 5],  # 关联的测试用例ID列表
    "execution_order": [1, 2, 3, 4, 5],  # 执行顺序（支持依赖排序）
    "env_config_id": 1,                  # 默认环境配置
    "concurrency_enabled": True,         # 是否启用并发
    "max_concurrency": 10,               # 最大并发数
    "status": "active"
}
```

#### 3.2.3 执行记录格式（test_execution表）

```python
test_execution = {
    "suite_id": 1,
    "env_id": 1,
    "start_time": "2026-03-19 10:00:00",
    "end_time": "2026-03-19 10:05:30",
    "total_count": 100,
    "passed_count": 95,
    "failed_count": 5,
    "skipped_count": 0,
    "duration_ms": 330000,
    "concurrency": 5,
    "results": [
        {
            "case_id": 1,
            "case_name": "创建客户_必填参数正常",
            "status": "passed",
            "duration_ms": 120,
            "response": {...},
            "assertions": [...],
            "error": None
        },
        {
            "case_id": 2,
            "case_name": "创建客户_身份证号格式错误",
            "status": "failed",
            "duration_ms": 85,
            "response": {...},
            "assertions": [...],
            "error": "预期状态码400，实际200"
        }
    ],
    "report_path": "/outputs/reports/execution_xxx/allure-report"
}
```

---

## 四、模块详细设计

### 4.1 API接口层

#### 4.1.1 新增API模块

```
api/
├── http_api_auto_test.py          # 新增：API自动化测试主接口
├── http_api_auto_test_parser.py   # 新增：文档解析子接口
└── http_api_auto_test_executor.py # 新增：测试执行子接口
```

#### 4.1.2 主接口代码框架

```python
# api/http_api_auto_test.py
from flask import Blueprint, request, jsonify

api_auto_test_bp = Blueprint("api_auto_test", __name__, url_prefix="/api/auto_test")

@api_auto_test_bp.route("/upload", methods=["POST"])
def upload_api_docs():
    """
    上传API文档
    支持：OpenAPI(.json/.yaml)、接口说明(.docx)、流程图(.png/.jpg)
    
    请求：
    - file: 文件
    - doc_type: api_doc | openapi | flowchart
    - system_name: 系统名称（可选，自动提取）
    
    返回：
    - doc_id: 文档ID
    - parsed_interfaces: 解析出的接口列表
    """
    pass

@api_auto_test_bp.route("/generate", methods=["POST"])
def generate_test_cases():
    """
    生成测试用例
    
    请求：
    - doc_id: 文档ID（上传后返回）
    - options: {
        "generate_mode": "normal" | "comprehensive",  # 常规/全面覆盖
        "include_boundary": true,   # 包含边界值测试
        "include_error": true,      # 包含异常测试
        "priority_filter": ["P0", "P1"]  # 优先级过滤
      }
    
    返回：
    - case_ids: 生成的测试用例ID列表
    - case_count: 用例数量
    - report: 生成报告
    """
    pass

@api_auto_test_bp.route("/execute", methods=["POST"])
def execute_tests():
    """
    执行测试用例
    
    请求：
    - case_ids: 用例ID列表
    - env_id: 环境配置ID
    - concurrency: 并发数（默认5）
    - mode: "serial" | "parallel"
    
    返回：
    - execution_id: 执行记录ID
    - summary: 执行摘要
    """
    pass

@api_auto_test_bp.route("/results/<execution_id>", methods=["GET"])
def get_execution_results(execution_id):
    """
    获取执行结果
    """
    pass

@api_auto_test_bp.route("/report/<execution_id>", methods=["GET"])
def download_report(execution_id):
    """
    下载测试报告（Allure格式）
    """
    pass
```

### 4.2 LLM智能层

#### 4.2.1 新增LLM模块

```
common/llm/
├── api_case_generator.py          # 扩展：API测试用例生成
├── api_doc_analyzer.py            # 新增：API文档分析器
└── flowchart_analyzer.py          # 新增：流程图分析器
```

#### 4.2.2 Prompt模板

```python
# common/llm/api_test_prompts.py

API_DOC_ANALYSIS_PROMPT = """
你是API测试专家。请分析以下API文档，提取接口信息：

【接口文档】
{api_doc_content}

请提取：
1. 接口名称和描述
2. 请求方法、路径、头部
3. 请求参数（名称、类型、必填、约束）
4. 响应参数（名称、类型、说明）
5. 可能的业务场景

以JSON格式输出：
{{
  "interface_name": "...",
  "description": "...",
  "method": "POST",
  "path": "/api/xxx",
  "request_params": [...],
  "response_params": [...],
  "scenarios": [...]
}}
"""

TEST_CASE_GENERATION_PROMPT = """
你是资深接口测试工程师。根据以下API信息，生成测试用例：

【API信息】
{api_info}

【参数约束】
{param_constraints}

生成要求：
1. 覆盖正向场景（必填参数正常、全部参数正常）
2. 覆盖边界值（最小值、最大值、超出范围）
3. 覆盖异常场景（必填参数缺失、参数格式错误、枚举值错误）
4. 覆盖关联场景（前置依赖接口）

每个用例包含：
- title: 用例标题
- description: 用例描述
- priority: P0/P1/P2/P3
- tags: 标签数组
- request: 请求参数
- expected: 期望结果
- preconditions: 前置条件

以JSON数组格式输出。
"""

FLOWCHART_ANALYSIS_PROMPT = """
你是业务流程分析专家。请分析以下流程图，提取：

1. 流程中的各个节点（接口/操作）
2. 节点之间的执行顺序和依赖关系
3. 每个节点的条件判断
4. 异常流程和错误处理

【流程描述】
{flowchart_description}

输出JSON：
{{
  "flow_name": "...",
  "nodes": [
    {{
      "id": "node_1",
      "name": "接口A",
      "type": "api",
      "params": {{}},
      "next_nodes": ["node_2", "node_3"],
      "conditions": {{}}
    }}
  ],
  "dependencies": [
    {{"from": "node_1", "to": "node_2", "param_mapping": {{"customerId": "customer_id"}}}}
  ]
}}
"""
```

### 4.3 RAG向量层

#### 4.3.1 复用现有模块

| 现有模块 | 复用方式 |
|---------|---------|
| `api_doc_processor.py` | 直接复用接口文档解析 |
| `vector_indexer.py` | 直接复用向量索引构建 |
| `document_classifier.py` | 扩展支持新文档类型 |

#### 4.3.2 新增处理器

```python
# common/rag/processors/api_auto_test_processor.py

class APITestDocProcessor:
    """API自动化测试文档处理器"""
    
    def process_openapi(self, doc_path: str) -> Dict[str, Any]:
        """处理OpenAPI 3.0文档"""
        # 解析Swagger/YAML
        # 提取接口列表
        # 构建接口依赖图
        pass
    
    def process_interface_doc(self, doc_path: str) -> Dict[str, Any]:
        """处理接口说明Word文档"""
        # 复用现有api_doc_processor
        # 提取表格参数
        # 关联请求响应
        pass
    
    def process_flowchart(self, image_path: str) -> Dict[str, Any]:
        """处理流程图图片"""
        # 调用LLM多模态分析
        # 提取业务流程节点
        # 构建执行顺序
        pass
```

### 4.4 测试执行层

#### 4.4.1 新增执行器模块

```
common/test_executor/
├── __init__.py
├── api_test_runner.py             # API测试运行器
├── test_generator.py              # 动态用例生成器
├── fixture_manager.py             # Fixtures管理器
├── parameter_resolver.py          # 参数替换器
├── assertion_engine.py            # 断言引擎
└── report_generator.py           # 报告生成器
```

#### 4.4.2 核心执行器代码

```python
# common/test_executor/api_test_runner.py

class APITestRunner:
    """API测试运行器"""
    
    def __init__(self, env_config: Dict, concurrency: int = 5):
        self.env_config = env_config
        self.concurrency = concurrency
        self.session = requests.Session()
        self.variables = {}  # 全局变量存储
        self.results = []
    
    def execute_case(self, test_case: Dict) -> TestResult:
        """执行单个测试用例"""
        # 1. 替换变量
        resolved_data = self._resolve_variables(test_case)
        
        # 2. 执行前置脚本
        self._run_setup_scripts(resolved_data)
        
        # 3. 发送请求
        response = self._send_request(resolved_data)
        
        # 4. 执行断言
        assertions = self._run_assertions(response, resolved_data)
        
        # 5. 提取并保存变量（用于后续用例）
        self._extract_variables(response, resolved_data)
        
        # 6. 执行后置脚本
        self._run_teardown_scripts(resolved_data)
        
        return TestResult(
            case_id=test_case.get("id"),
            status="passed" if all(a.passed for a in assertions) else "failed",
            assertions=assertions,
            response=response,
            duration=time.time() - start_time
        )
    
    def execute_batch(self, test_cases: List[Dict], mode: str = "parallel") -> List[TestResult]:
        """批量执行测试用例"""
        if mode == "parallel":
            with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
                futures = {executor.submit(self.execute_case, tc): tc for tc in test_cases}
                return [f.result() for f in as_completed(futures)]
        else:
            return [self.execute_case(tc) for tc in test_cases]
    
    def _resolve_variables(self, data: Any) -> Any:
        """递归替换变量 {{var_name}} 或 ${PREV.xxx}"""
        if isinstance(data, dict):
            return {k: self._resolve_variables(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._resolve_variables(item) for item in data]
        elif isinstance(data, str):
            # 替换全局变量 {{var_name}}
            for var_name, var_value in self.variables.items():
                if f"{{{{{var_name}}}}}" in data:
                    data = data.replace(f"{{{{{var_name}}}}}", str(var_value))
            # 替换前置接口变量 ${PREV.field}
            if "${PREV." in data:
                data = self._resolve_prev_variable(data)
            return data
        return data
    
    def _send_request(self, request_config: Dict) -> Response:
        """发送HTTP请求"""
        method = request_config.get("method", "GET").upper()
        path = request_config.get("path", "")
        headers = request_config.get("headers", {})
        params = request_config.get("query", {})
        body = request_config.get("body", {})
        timeout = request_config.get("timeout", 30)
        
        url = self._join_url(self.env_config.get("base_url"), path)
        
        return self.session.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=body,
            timeout=timeout
        )
```

#### 4.4.3 Fixture管理器

```python
# common/test_executor/fixture_manager.py

class FixtureManager:
    """Fixtures管理器"""
    
    # 内置Fixtures
    BUILTIN_FIXTURES = {
        "env_config": "load_environment_config",
        "api_client": "create_api_client",
        "auth_token": "get_auth_token",
        "test_data": "load_test_data",
        "db_connection": "get_db_connection",
    }
    
    def __init__(self):
        self.fixtures = {}
    
    def register_fixture(self, name: str, factory_func: Callable):
        """注册自定义fixture"""
        self.fixtures[name] = factory_func
    
    def get_fixture(self, name: str, scope: str = "function") -> Any:
        """获取fixture实例"""
        if name not in self.fixtures:
            if name in self.BUILTIN_FIXTURES:
                factory = getattr(self, self.BUILTIN_FIXTURES[name])
                self.fixtures[name] = factory()
            else:
                raise ValueError(f"Unknown fixture: {name}")
        return self.fixtures[name]
    
    def load_environment_config(self, env_id: int) -> Dict:
        """加载环境配置"""
        from common.db_mapper.environment_config_mapper import EnvironmentConfigMapper
        mapper = EnvironmentConfigMapper()
        env = mapper.get_by_id(env_id)
        return env.to_json() if env else {}
    
    def create_api_client(self, env_config: Dict) -> requests.Session:
        """创建API客户端"""
        session = requests.Session()
        session.headers.update(env_config.get("headers", {}))
        return session
    
    def cleanup(self):
        """清理所有fixtures"""
        for name, fixture in self.fixtures.items():
            if hasattr(fixture, "close"):
                fixture.close()
        self.fixtures.clear()
```

---

## 五、接口对接文档

### 5.1 前端对接接口

#### 5.1.1 上传API文档

**请求**

```http
POST /api/auto_test/upload
Content-Type: multipart/form-data

file: [文件]
doc_type: openapi|api_doc|flowchart
system_name: 普通收单系统
```

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "doc_id": "uuid-xxx",
    "doc_type": "openapi",
    "system_name": "普通收单系统",
    "parsed_interfaces": [
      {
        "name": "创建客户",
        "method": "POST",
        "path": "/api/customer/create",
        "request_params_count": 5,
        "response_params_count": 3
      },
      {
        "name": "查询客户",
        "method": "GET",
        "path": "/api/customer/query",
        "request_params_count": 2,
        "response_params_count": 5
      }
    ],
    "flowchart_nodes": [
      {"id": "1", "name": "创建客户", "next": ["2"]},
      {"id": "2", "name": "绑定银行卡", "next": ["3"]},
      {"id": "3", "name": "下单", "next": []}
    ]
  }
}
```

#### 5.1.2 生成测试用例

**请求**

```http
POST /api/auto_test/generate
Content-Type: application/json

{
  "doc_id": "uuid-xxx",
  "system_name": "普通收单系统",
  "options": {
    "generate_mode": "comprehensive",
    "include_boundary": true,
    "include_error": true,
    "include_dependency": true,
    "priority_filter": ["P0", "P1", "P2"]
  }
}
```

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "doc_id": "uuid-xxx",
    "case_ids": [101, 102, 103, 104, 105],
    "case_count": 5,
    "cases": [
      {
        "id": 101,
        "name": "创建客户_必填参数正常",
        "priority": "P0",
        "tags": ["正向", "必填"]
      },
      {
        "id": 102,
        "name": "创建客户_身份证号格式错误",
        "priority": "P1",
        "tags": ["异常", "参数校验"]
      }
    ],
    "report": {
      "total": 5,
      "by_priority": {"P0": 1, "P1": 2, "P2": 2},
      "by_tag": {"正向": 1, "异常": 2, "边界": 2}
    }
  }
}
```

#### 5.1.3 执行测试

**请求**

```http
POST /api/auto_test/execute
Content-Type: application/json

{
  "case_ids": [101, 102, 103],
  "env_id": 1,
  "concurrency": 5,
  "mode": "parallel"
}
```

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "execution_id": "exec-xxx",
    "status": "running",
    "summary": {
      "total": 3,
      "passed": 2,
      "failed": 1,
      "running": 0
    },
    "progress_url": "/api/auto_test/results/exec-xxx"
  }
}
```

#### 5.1.4 查询执行结果

**请求**

```http
GET /api/auto_test/results/exec-xxx
```

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "execution_id": "exec-xxx",
    "status": "completed",
    "start_time": "2026-03-19 10:00:00",
    "end_time": "2026-03-19 10:05:30",
    "duration_ms": 330000,
    "summary": {
      "total": 100,
      "passed": 95,
      "failed": 5,
      "success_rate": 95.0
    },
    "results": [
      {
        "case_id": 101,
        "case_name": "创建客户_必填参数正常",
        "status": "passed",
        "duration_ms": 120,
        "response_time_ms": 85,
        "assertions": [
          {"name": "状态码断言", "passed": true},
          {"name": "响应时间断言", "passed": true}
        ]
      },
      {
        "case_id": 102,
        "case_name": "创建客户_身份证号格式错误",
        "status": "failed",
        "duration_ms": 85,
        "error": "预期状态码400，实际200",
        "actual_response": {...},
        "expected_response": {...}
      }
    ],
    "report_url": "/api/auto_test/report/exec-xxx"
  }
}
```

---

## 六、向后兼容设计

### 6.1 不影响现有功能

| 现有功能 | 保障措施 |
|---------|---------|
| 现有测试用例管理 | 新增表结构，不修改现有表 |
| 现有执行接口 | 新增独立执行路径，不修改原接口 |
| 现有RAG服务 | 复用现有模块，不修改原代码 |
| 现有数据库连接 | 使用现有db_session，不改变配置 |

### 6.2 命名隔离

```python
# 新增表前缀隔离
crosstest_test_case          # 现有表（不动）
crosstest_test_case_auto     # 新增：API自动生成的用例（可选，通过case_type区分）

# 新增字段（可选扩展）
# test_case表新增 case_type 字段
case_type: "manual" | "auto_generated"
```

---

## 七、扩展性设计

### 7.1 支持多种文档格式

| 文档类型 | 处理器 | 状态 |
|---------|-------|------|
| OpenAPI 3.0 (JSON) | `openapi_parser.py` | 新增 |
| OpenAPI 3.0 (YAML) | `openapi_parser.py` | 新增 |
| Swagger 2.0 | `swagger_parser.py` | 新增 |
| 接口说明文档 (DOCX) | `api_doc_processor.py` | 复用 |
| Postman Collection | `postman_parser.py` | 计划中 |
| HAR 文件 | `har_parser.py` | 计划中 |

### 7.2 支持多种测试场景

| 测试场景 | 实现方式 | 状态 |
|---------|---------|------|
| 正向用例 | 自动生成 | 实现 |
| 边界值测试 | 自动生成 | 实现 |
| 异常测试 | 自动生成 | 实现 |
| 依赖链测试 | 流程图分析 | 实现 |
| 数据驱动测试 | CSV/JSON数据源 | 计划中 |
| 场景测试 | 多接口组合 | 计划中 |

---

## 八、部署与配置

### 8.1 新增配置文件

```json
// app/config/api_auto_test_config.json
{
  "llm": {
    "provider": "dashscope",
    "model": "qwen-plus",
    "temperature": 0.7,
    "max_tokens": 2000
  },
  "test_execution": {
    "default_concurrency": 5,
    "max_concurrency": 20,
    "default_timeout": 30,
    "retry_times": 2
  },
  "storage": {
    "upload_dir": "uploads/api_auto_test",
    "report_dir": "outputs/reports"
  }
}
```

### 8.2 数据库扩展

```sql
-- 可选：为现有test_case表添加类型标识
ALTER TABLE crosstest_test_case 
ADD COLUMN case_type VARCHAR(20) DEFAULT 'manual' COMMENT '用例类型: manual-手动, auto-自动生成';

-- 新增接口依赖关系表
CREATE TABLE crosstest_api_dependency (
    id INT PRIMARY KEY AUTO_INCREMENT,
    source_case_id INT NOT NULL COMMENT '源用例ID',
    target_case_id INT NOT NULL COMMENT '目标用例ID',
    param_mapping JSON COMMENT '参数映射关系',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_case_id) REFERENCES crosstest_test_case(id),
    FOREIGN KEY (target_case_id) REFERENCES crosstest_test_case(id)
);
```

---

## 九、风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|---------|
| LLM输出不稳定 | 用例格式不规范 | 添加输出校验和JSON修复 |
| 文档格式多样 | 解析失败 | 多种解析器fallback |
| 接口依赖复杂 | 参数传递错误 | 可视化依赖配置界面 |
| 执行超时 | 测试卡住 | 超时控制和优雅终止 |
| 并发冲突 | 数据竞争 | 事务隔离和重试机制 |

---

## 十、里程碑计划

| 阶段 | 功能 | 交付物 |
|------|------|-------|
| Phase 1 | 基础框架搭建 | API接口、文档解析、基础执行 |
| Phase 2 | AI增强能力 | LLM用例生成、流程图分析 |
| Phase 3 | 高级特性 | 并发执行、依赖管理、报告优化 |
| Phase 4 | 生产完善 | 性能优化、监控告警、CI/CD集成 |

---

*文档版本: v0.1*
*创建日期: 2026-03-19*
*作者: AI架构助手*
