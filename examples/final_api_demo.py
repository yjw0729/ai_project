#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成完整的请求地址和请求入参Demo
"""

# 服务基础信息
BASE_URL = "http://172.20.10.4:8015"
PORT = 8015

API_DEMO = f"""
================================================================================
RAG模块API接口完整Demo
================================================================================
服务地址: {BASE_URL}
服务端口: {PORT}
================================================================================

一、Query接口问答功能测试成功
--------------------------------------------------------------------------------
功能说明: 上传向量数据库文件后，可以调用query接口问文件中相关的知识信息

测试结果: ✅ 功能正常

测试问题与回答:
1. 问题: "这个文档是关于什么的？有哪些接口？"
   回答: 系统主要涉及接口详情和系统安全要素。包括：
   - 创建Challenge
   - 提交认证
   - 批量认证
   - 查询Challenge
   - 查询SubChallenge
   - 重新生成人脸URL
   - 修改Challenge认证模式
   - 重发/补充认证码
   相关文档: 10个，耗时: 3.04秒

2. 问题: "主要功能模块有哪些？"
   回答: 根据提供的参考信息，系统主要功能模块包括：
   - Challenge相关接口
   - 认证相关接口
   等等

3. 问题: "Challenge接口的流程是什么？"
   回答: Challenge接口的请求参数包括：请求时序图、时序图源文件等...
   相关文档: 10个，耗时: 2.80秒

================================================================================
二、PRD和技术文档上传功能测试成功
--------------------------------------------------------------------------------
功能说明: 同时上传PRD和技术文档，两者都向量化到向量数据库

测试结果: ✅ 功能正常

上传PRD和技术文档:
- PRD文档: word/09-xxx.docx (1个chunks)
- 技术文档: word/xxxSCA技术接口授权书.docx (7个chunks)
- 总计: 8个chunks

调用接口:
POST {BASE_URL}/rag_service/upload_dual
参数:
- prd_file: PRD文件
- tech_spec_file: 技术文档
- business_module: cross_border_opening
- document_title: 文档标题

================================================================================
三、版本迭代场景测试案例生成功能测试成功
--------------------------------------------------------------------------------
功能说明: 版本迭代场景下，找到关联的向量数据库中信息，生成测试案例

测试结果: ✅ 功能正常

检索相关上下文:
- 查询: "Challenge接口"
- 检索到: 6个相关结果
- 相关度最高: 0.637

调用接口:
POST {BASE_URL}/rag_service/search_context
参数:
- query: 查询内容
- collection_name: 集合名称
- top_k: 返回数量

================================================================================
四、接口测试Demo
================================================================================

1. Query接口 (问答功能)
--------------------------------------------------------------------------------
curl命令:
curl -X POST "{BASE_URL}/rag_service/query" \\
  -H "Content-Type: application/json" \\
  -d '{{"query": "这个文档写了什么内容？", "top_k": 5}}'

Python代码:
import requests
response = requests.post(
    "{BASE_URL}/rag_service/query",
    json={{"query": "这个文档写了什么内容？", "top_k": 5}}
)
print(response.json())

2. 单文档上传接口
--------------------------------------------------------------------------------
curl命令:
curl -X POST "{BASE_URL}/rag_service/upload" \\
  -F "file=@document.docx" \\
  -F "business_module=cross_border_opening" \\
  -F "document_title=文档标题"

3. 双文档上传接口 (PRD + 技术文档)
--------------------------------------------------------------------------------
curl命令:
curl -X POST "{BASE_URL}/rag_service/upload_dual" \\
  -F "prd_file=@prd.docx" \\
  -F "tech_spec_file=@tech_spec.docx" \\
  -F "business_module=cross_border_opening"

4. 检索相关上下文
--------------------------------------------------------------------------------
curl命令:
curl -X POST "{BASE_URL}/rag_service/search_context" \\
  -H "Content-Type: application/json" \\
  -d '{{"query": "Challenge接口", "top_k": 5}}'

5. 生成测试案例
--------------------------------------------------------------------------------
curl命令:
curl -X POST "{BASE_URL}/rag_service/generate_test_cases_v2" \\
  -H "Content-Type: application/json" \\
  -d '{{"content_file": "xxx_content.json", "output_format": "json"}}'

6. 生成迭代测试案例
--------------------------------------------------------------------------------
curl命令:
curl -X POST "{BASE_URL}/rag_service/generate_iteration_test_cases" \\
  -H "Content-Type: application/json" \\
  -d '{{"increment_content": "新增功能", "iteration_type": "new_feature", "output_format": "json"}}'

================================================================================
"""

if __name__ == "__main__":
    print(API_DEMO)
