"""
API自动化测试专用的Prompt模板。
"""

# ============ API文档分析 ============
API_DOC_ANALYSIS_PROMPT = """你是API测试专家。请分析以下API文档，提取接口信息。

【接口文档】
{api_doc_content}

请提取：
1. 接口名称和描述
2. 请求方法、路径、头部
3. 请求参数（名称、类型、必填、约束、示例值）
4. 响应参数（名称、类型、说明）
5. 可能的业务场景
6. 参数校验规则（格式、长度、枚举值等）

以JSON格式输出：
{{
  "interface_name": "...",
  "description": "...",
  "method": "POST",
  "path": "/api/xxx",
  "headers": {{}},
  "request_params": [
    {{
      "name": "参数名",
      "type": "string",
      "required": true,
      "description": "参数说明",
      "constraints": "格式/长度/枚举约束",
      "example": "示例值"
    }}
  ],
  "response_params": [
    {{
      "name": "响应字段名",
      "type": "string",
      "description": "字段说明"
    }}
  ],
  "scenarios": ["场景1", "场景2"]
}}"""

# ============ 测试用例生成 ============
TEST_CASE_GENERATION_PROMPT = """你是资深接口测试工程师。根据以下API信息，生成测试用例。

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
- id: 用例唯一标识
- title: 用例标题（简洁明了）
- description: 用例描述
- priority: P0/P1/P2/P3（P0为核心流程）
- tags: 标签数组，如["正向","必填"]或["异常","参数校验"]
- request: 请求配置 {{method, path, headers, query, body}}
- expect: 期望结果描述
- status_code: 期望HTTP状态码
- assertions: 断言数组，如["status_code == 200", "response.code == 0"]

以JSON数组格式输出，不要输出多余文本。
"""

# ============ 流程图分析 ============
FLOWCHART_ANALYSIS_PROMPT = """你是业务流程分析专家。请分析以下流程图或流程描述，提取：

1. 流程中的各个节点（接口/操作）
2. 节点之间的执行顺序和依赖关系
3. 每个节点的条件判断
4. 异常流程和错误处理
5. 关键业务参数及其传递关系

【流程描述】
{flowchart_description}

输出JSON：
{{
  "flow_name": "流程名称",
  "nodes": [
    {{
      "id": "node_1",
      "name": "节点名称（接口/操作名）",
      "type": "api|condition|action",
      "api_path": "/api/xxx",  // 仅type=api时
      "method": "POST",        // 仅type=api时
      "params": {{}},          // 节点所需参数
      "next_nodes": ["node_2", "node_3"],  // 后续节点
      "conditions": {{}}       // 条件判断
    }}
  ],
  "dependencies": [
    {{
      "from": "node_1",
      "to": "node_2",
      "param_mapping": {{"customerId": "customer_id"}},
      "description": "参数传递说明"
    }}
  ],
  "entry_point": "node_1",
  "critical_paths": [["node_1", "node_2", "node_4"]]
}}"""

# ============ OpenAPI解析增强 ============
OPENAPI_ENHANCE_PROMPT = """你是API测试专家。请分析以下OpenAPI/Swagger文档，提取更详细的测试信息。

【OpenAPI文档】
{openapi_content}

请提取每个接口的：
1. 完整的参数定义（包括嵌套对象的每个字段）
2. 参数的校验约束（min/max length, pattern, enum等）
3. 响应状态码和响应体结构
4. 认证方式（Bearer Token, API Key等）
5. 可能的错误响应

以JSON格式输出：
{{
  "interfaces": [
    {{
      "path": "/api/xxx",
      "method": "POST",
      "summary": "接口描述",
      "parameters": [...],
      "request_body": {{...}},
      "responses": {{...}},
      "security": [...]
    }}
  ]
}}"""

# ============ 测试数据生成 ============
TEST_DATA_GENERATION_PROMPT = """你是测试数据工程师。根据以下API参数定义，生成合理的测试数据。

【参数定义】
{param_definitions}

【要求】
1. 正常值：符合所有约束的有效数据
2. 边界值：正好在边界上、刚好超出边界
3. 异常值：格式错误、类型错误、空值等
4. 特殊值：空字符串、null、超长字符串、SQL注入、XSS等

输出JSON数组，每个元素包含：
{{
  "param_name": "参数名",
  "value": "测试值",
  "type": "normal|boundary|error|special",
  "description": "数据说明"
}}"""
