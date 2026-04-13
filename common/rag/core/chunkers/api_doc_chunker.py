#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API文档专用分块器
针对API接口文档的结构化分块策略，保持API端点的完整性
"""

import re
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class APIEndpoint:
    """API端点信息"""
    path: str
    method: str
    description: str
    parameters: List[Dict] = field(default_factory=list)
    responses: List[Dict] = field(default_factory=list)
    request_body: Optional[Dict] = None
    headers: List[Dict] = field(default_factory=list)
    auth: Optional[str] = None


class APIDocChunker:
    """
    API文档分块器
    
    专门处理API接口文档，保持每个接口的完整性：
    - 基础信息（路径、方法、描述）
    - 请求参数
    - 请求体
    - 响应格式
    - 错误码说明
    
    分块策略：
    1. 首先识别文档中的所有API端点
    2. 为每个端点创建完整的上下文块
    3. 必要时进行二次分割（超长内容）
    """
    
    def __init__(self, chunk_size: int = 800, overlap: int = 100):
        """
        初始化API文档分块器
        
        Args:
            chunk_size: 目标块大小
            overlap: 块之间的重叠大小
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        
        # HTTP方法
        self.http_methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]
        
        # 参数区域标识
        self.param_section_keywords = [
            "请求参数", "参数说明", "参数列表", "Query Parameters",
            "Request Parameters", "path parameters", "header parameters",
            "请求头", "请求体", "Request Body"
        ]
        
        # 响应区域标识
        self.response_section_keywords = [
            "响应", "返回", "Response", "返回结果", "返回参数"
        ]
        
        logger.info(f"API文档分块器初始化: chunk_size={chunk_size}, overlap={overlap}")
    
    def chunk(self, content: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        对API文档进行分块
        
        Args:
            content: 文档内容
            metadata: 元数据
            
        Returns:
            分块结果列表
        """
        if not content:
            return []
        
        metadata = metadata or {}
        
        # 1. 提取API端点
        endpoints = self._extract_endpoints(content)
        
        if endpoints:
            # 找到了API端点，使用端点导向分块
            return self._chunk_by_endpoints(endpoints, metadata)
        else:
            # 没有找到端点，回退到结构化分块
            return self._fallback_chunking(content, metadata)
    
    def _extract_endpoints(self, content: str) -> List[APIEndpoint]:
        """提取文档中的所有API端点"""
        endpoints = []
        lines = content.split('\n')
        
        current_endpoint = None
        current_section = "description"
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # 检测新的API端点
            endpoint_match = self._detect_endpoint(line)
            if endpoint_match:
                # 保存之前的端点
                if current_endpoint:
                    endpoints.append(current_endpoint)
                
                # 创建新端点
                method, path = endpoint_match
                current_endpoint = APIEndpoint(
                    path=path,
                    method=method,
                    description=""
                )
                current_section = "description"
                continue
            
            # 检测当前所在的区域
            section = self._detect_section(line)
            if section:
                current_section = section
                continue
            
            # 收集端点信息
            if current_endpoint:
                self._parse_endpoint_line(current_endpoint, line, current_section)
        
        # 保存最后一个端点
        if current_endpoint:
            endpoints.append(current_endpoint)
        
        logger.info(f"提取到 {len(endpoints)} 个API端点")
        return endpoints
    
    def _detect_endpoint(self, line: str) -> Optional[Tuple[str, str]]:
        """
        检测API端点
        
        支持格式：
        - GET /api/users
        - POST /api/users/create
        - [GET] /api/users
        - 接口: GET /api/users
        """
        line = line.strip()
        
        # 格式1: METHOD /path
        pattern1 = r'^(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\s+(/\S+)'
        match = re.match(pattern1, line, re.IGNORECASE)
        if match:
            return match.group(1).upper(), match.group(2)
        
        # 格式2: [METHOD] /path
        pattern2 = r'^\[(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\]\s*(/\S+)'
        match = re.match(pattern2, line, re.IGNORECASE)
        if match:
            return match.group(1).upper(), match.group(2)
        
        # 格式3: 接口: METHOD /path
        pattern3 = r'接口[：:]\s*(GET|POST|PUT|DELETE|PATCH)\s+(/\S+)'
        match = re.match(pattern3, line, re.IGNORECASE)
        if match:
            return match.group(1).upper(), match.group(2)
        
        return None
    
    def _detect_section(self, line: str) -> Optional[str]:
        """检测当前所在的区域"""
        line_lower = line.lower()
        
        # 参数区域
        for keyword in self.param_section_keywords:
            if keyword.lower() in line_lower:
                return "parameters"
        
        # 响应区域
        for keyword in self.response_section_keywords:
            if keyword.lower() in line_lower:
                return "response"
        
        return None
    
    def _parse_endpoint_line(self, endpoint: APIEndpoint, line: str, section: str):
        """解析端点的行内容"""
        line = line.strip()
        if not line:
            return
        
        # 描述区域
        if section == "description":
            if endpoint.description:
                endpoint.description += " " + line
            else:
                endpoint.description = line
        
        # 参数区域 - 简单的键值对解析
        elif section == "parameters":
            # 尝试解析表格格式或列表格式
            param = self._parse_parameter_line(line)
            if param:
                endpoint.parameters.append(param)
        
        # 响应区域
        elif section == "response":
            resp = self._parse_response_line(line)
            if resp:
                endpoint.responses.append(resp)
    
    def _parse_parameter_line(self, line: str) -> Optional[Dict]:
        """解析参数行"""
        # 格式: name | type | required | description
        # 格式: name (type): description
        # 格式: name - type - description
        
        # 尝试多种分隔符
        for sep in ['|', '\t', '-', ':']:
            parts = [p.strip() for p in line.split(sep)]
            if len(parts) >= 2:
                return {
                    "name": parts[0],
                    "type": parts[1] if len(parts) > 1 else "string",
                    "description": parts[-1] if len(parts) > 2 else "",
                    "required": "必填" in line or "required" in line.lower()
                }
        
        return None
    
    def _parse_response_line(self, line: str) -> Optional[Dict]:
        """解析响应行"""
        # 格式: 200 - success - description
        # 格式: 404 - Not Found
        
        match = re.match(r'^(\d{3})\s*[-–]\s*(\S+)(.*)', line)
        if match:
            return {
                "code": match.group(1),
                "status": match.group(2),
                "description": match.group(3).strip() if match.group(3) else ""
            }
        
        return None
    
    def _chunk_by_endpoints(
        self, 
        endpoints: List[APIEndpoint], 
        metadata: Dict
    ) -> List[Dict[str, Any]]:
        """基于端点进行分块"""
        chunks = []
        
        for i, endpoint in enumerate(endpoints):
            # 构建完整的端点上下文
            chunk_content = self._build_endpoint_context(endpoint)
            
            # 检查是否需要二次分割
            if len(chunk_content) > self.chunk_size * 1.5:
                # 需要分割
                sub_chunks = self._split_large_endpoint(endpoint, chunk_content, i, metadata)
                chunks.extend(sub_chunks)
            else:
                # 直接添加
                chunks.append({
                    "content": chunk_content,
                    "metadata": {
                        **metadata,
                        "doc_type": "api_doc",
                        "chunk_type": "api_endpoint",
                        "api_path": endpoint.path,
                        "api_method": endpoint.method,
                        "endpoint_index": i,
                        "total_endpoints": len(endpoints)
                    }
                })
        
        return chunks
    
    def _build_endpoint_context(self, endpoint: APIEndpoint) -> str:
        """构建端点的完整上下文"""
        parts = []
        
        # 标题
        parts.append(f"## {endpoint.method} {endpoint.path}")
        
        # 描述
        if endpoint.description:
            parts.append(f"\n描述: {endpoint.description}")
        
        # 认证
        if endpoint.auth:
            parts.append(f"\n认证方式: {endpoint.auth}")
        
        # 请求参数
        if endpoint.parameters:
            parts.append("\n### 请求参数")
            for param in endpoint.parameters:
                required = "必填" if param.get("required") else "可选"
                parts.append(
                    f"- {param.get('name', '')} ({param.get('type', 'string')}) [{required}]: "
                    f"{param.get('description', '')}"
                )
        
        # 请求体
        if endpoint.request_body:
            parts.append("\n### 请求体")
            parts.append("```json")
            parts.append(json.dumps(endpoint.request_body, ensure_ascii=False, indent=2))
            parts.append("```")
        
        # 响应
        if endpoint.responses:
            parts.append("\n### 响应")
            for resp in endpoint.responses:
                parts.append(
                    f"- {resp.get('code', '')} {resp.get('status', '')}: "
                    f"{resp.get('description', '')}"
                )
        
        return "\n".join(parts)
    
    def _split_large_endpoint(
        self, 
        endpoint: APIEndpoint, 
        content: str, 
        index: int,
        metadata: Dict
    ) -> List[Dict[str, Any]]:
        """分割过大的端点块"""
        chunks = []
        
        # 基础信息块
        base_content = f"## {endpoint.method} {endpoint.path}\n\n"
        if endpoint.description:
            base_content += f"描述: {endpoint.description}\n"
        if endpoint.auth:
            base_content += f"认证方式: {endpoint.auth}\n"
        
        chunks.append({
            "content": base_content.strip(),
            "metadata": {
                **metadata,
                "doc_type": "api_doc",
                "chunk_type": "api_base",
                "api_path": endpoint.path,
                "api_method": endpoint.method,
                "endpoint_index": index
            }
        })
        
        # 参数块
        if endpoint.parameters:
            param_content = f"### {endpoint.method} {endpoint.path} - 请求参数\n\n"
            for param in endpoint.parameters:
                required = "必填" if param.get("required") else "可选"
                param_content += (
                    f"- {param.get('name', '')} ({param.get('type', 'string')}) "
                    f"[{required}]: {param.get('description', '')}\n"
                )
            
            chunks.append({
                "content": param_content.strip(),
                "metadata": {
                    **metadata,
                    "doc_type": "api_doc",
                    "chunk_type": "api_parameters",
                    "api_path": endpoint.path,
                    "api_method": endpoint.method,
                    "endpoint_index": index
                }
            })
        
        # 响应块
        if endpoint.responses:
            resp_content = f"### {endpoint.method} {endpoint.path} - 响应说明\n\n"
            for resp in endpoint.responses:
                resp_content += (
                    f"- {resp.get('code', '')} {resp.get('status', '')}: "
                    f"{resp.get('description', '')}\n"
                )
            
            chunks.append({
                "content": resp_content.strip(),
                "metadata": {
                    **metadata,
                    "doc_type": "api_doc",
                    "chunk_type": "api_response",
                    "api_path": endpoint.path,
                    "api_method": endpoint.method,
                    "endpoint_index": index
                }
            })
        
        return chunks
    
    def _fallback_chunking(self, content: str, metadata: Dict) -> List[Dict[str, Any]]:
        """备用分块策略 - 基于段落和标题"""
        chunks = []
        
        # 按段落分割
        paragraphs = re.split(r'\n\s*\n', content)
        
        current_chunk = []
        current_size = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # 检查是否是标题行
            is_heading = bool(re.match(r'^#{1,6}\s+', para)) or bool(
                re.match(r'^\d+[\.\)]\s+', para)
            )
            
            para_size = len(para)
            
            # 如果加上当前段落会超过限制，先保存当前块
            if current_size + para_size > self.chunk_size and current_chunk:
                chunks.append({
                    "content": "\n\n".join(current_chunk),
                    "metadata": {
                        **metadata,
                        "doc_type": "api_doc",
                        "chunk_type": "paragraph"
                    }
                })
                current_chunk = []
                current_size = 0
            
            current_chunk.append(para)
            current_size += para_size + 2  # +2 for newline
        
        # 处理最后一块
        if current_chunk:
            chunks.append({
                "content": "\n\n".join(current_chunk),
                "metadata": {
                    **metadata,
                    "doc_type": "api_doc",
                    "chunk_type": "paragraph"
                }
            })
        
        return chunks


def chunk_api_document(
    content: str, 
    chunk_size: int = 800, 
    overlap: int = 100,
    metadata: Dict = None
) -> List[Dict[str, Any]]:
    """
    便捷函数：对API文档进行分块
    
    Args:
        content: 文档内容
        chunk_size: 目标块大小
        overlap: 块之间的重叠大小
        metadata: 元数据
        
    Returns:
        分块结果列表
    """
    chunker = APIDocChunker(chunk_size=chunk_size, overlap=overlap)
    return chunker.chunk(content, metadata)

