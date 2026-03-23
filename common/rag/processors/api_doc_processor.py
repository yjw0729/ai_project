#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API文档专用处理器
针对API接口文档的智能处理：端点提取、参数解析、响应格式识别
"""

import re
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class HttpMethod(Enum):
    """HTTP方法枚举"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    OPTIONS = "OPTIONS"
    HEAD = "HEAD"


@dataclass
class APIEndpoint:
    """API端点信息"""
    path: str
    method: str
    description: str = ""
    parameters: List[Dict] = field(default_factory=list)
    request_body: Optional[Dict] = None
    response: Optional[Dict] = None
    status_codes: List[Dict] = field(default_factory=list)
    security: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


@dataclass
class APIParameter:
    """API参数信息"""
    name: str
    location: str  # path, query, header, body
    param_type: str
    required: bool = False
    description: str = ""
    default_value: Any = None
    enum_values: List[Any] = field(default_factory=list)
    example: Any = None


class APIDocumentProcessor:
    """API文档专用处理器"""
    
    def __init__(self):
        # HTTP方法模式
        self.method_patterns = [
            re.compile(r'^\s*(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\s+', re.IGNORECASE),
            re.compile(r'(请求方法|HTTP方法|Method)\s*[:：]?\s*(GET|POST|PUT|DELETE|PATCH)', re.IGNORECASE),
        ]
        
        # API路径模式
        self.path_patterns = [
            re.compile(r'(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\s+(/[\w\-/{}._~:/?#\[\]@!$&\'()*+,;=%]+)', re.IGNORECASE),
            re.compile(r'(接口地址|Endpoint|URL|请求路径|Path)\s*[:：]?\s*(/[\w\-/{}._~:/?#\[\]@!$&\'()*+,;=%]+)', re.IGNORECASE),
            re.compile(r'(/api/[\w\-/{}]+)'),
        ]
        
        # 参数表格模式
        self.param_table_patterns = [
            # Markdown表格
            re.compile(r'\|(.+?)\|(.+?)\|(.+?)\|(.+?)\|', re.MULTILINE),
            # 参数名称模式
            re.compile(r'(参数名|参数名称|字段|Field|Name)\s*[:：]\s*(\w+)', re.IGNORECASE),
        ]
        
        # 参数位置模式
        self.param_location_keywords = {
            'path': ['path', '路径参数', 'uri', 'url参数'],
            'query': ['query', '查询参数', '请求参数', 'url参数'],
            'header': ['header', '请求头', '头部参数'],
            'body': ['body', '请求体', 'request body', 'payload'],
        }
        
        # 数据类型模式
        self.type_keywords = {
            'string': ['string', 'str', '字符串', '文本'],
            'integer': ['integer', 'int', '整数', '数字'],
            'number': ['number', 'float', 'double', '数值', '浮点数'],
            'boolean': ['boolean', 'bool', '布尔', '真假'],
            'array': ['array', 'list', '数组', '列表'],
            'object': ['object', '对象', 'json'],
            'file': ['file', '文件', 'binary'],
        }
    
    def process(self, content: str, metadata: Dict = None) -> Tuple[List, Dict]:
        """
        处理API文档内容
        
        Args:
            content: 文档内容
            metadata: 元数据
            
        Returns:
            (处理后的文本块列表, 提取的元数据)
        """
        # 1. 提取API端点信息
        endpoints = self._extract_endpoints(content)
        
        # 2. 提取参数信息
        parameters = self._extract_parameters(content)
        
        # 3. 提取响应信息
        responses = self._extract_responses(content)
        
        # 4. 提取状态码
        status_codes = self._extract_status_codes(content)
        
        # 5. 构建增强的文档表示
        enhanced_content = self._build_enhanced_content(content, endpoints, parameters, responses)
        
        # 6. 构建元数据
        extracted_metadata = {
            'api_endpoints': [{
                'path': e.path,
                'method': e.method,
                'description': e.description,
            } for e in endpoints],
            'api_parameters': parameters,
            'api_responses': responses,
            'status_codes': status_codes,
            'doc_type': 'api_doc',
        }
        
        if metadata:
            extracted_metadata.update(metadata)
        
        # 7. 分块处理
        chunks = self._chunk_api_document(enhanced_content, extracted_metadata)
        
        logger.info(f"API文档处理完成: 发现 {len(endpoints)} 个端点, {len(chunks)} 个块")
        
        return chunks, extracted_metadata
    
    def _extract_endpoints(self, content: str) -> List[APIEndpoint]:
        """提取API端点"""
        endpoints = []
        lines = content.split('\n')
        
        current_endpoint = None
        current_description = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # 检查是否是HTTP方法行
            method_match = self.method_patterns[0].match(line)
            if method_match:
                # 保存之前的端点
                if current_endpoint:
                    current_endpoint.description = '\n'.join(current_description).strip()
                    endpoints.append(current_endpoint)
                
                method = method_match.group(1).upper()
                path_match = self.method_patterns[0].match(line)
                path = path_match.group(2) if path_match else ""
                
                current_endpoint = APIEndpoint(
                    path=path,
                    method=method,
                )
                current_description = []
                continue
            
            # 检查是否是接口路径描述行
            for pattern in self.path_patterns:
                match = pattern.search(line)
                if match:
                    if len(match.groups()) >= 2:
                        potential_method = match.group(1).upper()
                        potential_path = match.group(2)
                        
                        # 验证是否是有效的HTTP方法
                        if potential_method in [m.value for m in HttpMethod]:
                            if current_endpoint:
                                current_endpoint.description = '\n'.join(current_description).strip()
                                endpoints.append(current_endpoint)
                            
                            current_endpoint = APIEndpoint(
                                path=potential_path,
                                method=potential_method,
                            )
                            current_description = []
                            break
                        elif potential_path.startswith('/'):
                            if current_endpoint:
                                current_endpoint.description = '\n'.join(current_description).strip()
                                endpoints.append(current_endpoint)
                            
                            current_endpoint = APIEndpoint(
                                path=potential_path,
                                method="GET",  # 默认GET
                            )
                            current_description = []
                            break
            
            # 收集描述信息
            if current_endpoint and line and not line.startswith('|') and not line.startswith('-'):
                current_description.append(line)
        
        # 保存最后一个端点
        if current_endpoint:
            current_endpoint.description = '\n'.join(current_description).strip()
            endpoints.append(current_endpoint)
        
        logger.debug(f"提取到 {len(endpoints)} 个API端点")
        return endpoints
    
    def _extract_parameters(self, content: str) -> List[Dict]:
        """提取参数信息"""
        parameters = []
        
        # 查找参数表格
        param_sections = self._find_parameter_sections(content)
        
        for section in param_sections:
            # 解析表格内容
            table_params = self._parse_parameter_table(section)
            parameters.extend(table_params)
        
        return parameters
    
    def _find_parameter_sections(self, content: str) -> List[str]:
        """查找参数相关章节"""
        sections = []
        lines = content.split('\n')
        
        in_param_section = False
        current_section = []
        param_keywords = ['参数', 'parameter', 'field', '字段', '请求参数', 'Request Parameters']
        
        for line in lines:
            # 检查是否是参数章节开始
            if any(kw in line.lower() for kw in param_keywords):
                if not in_param_section:
                    in_param_section = True
                    current_section = []
            
            if in_param_section:
                # 检查是否到达新章节（通常是空行或新的标题）
                if line.strip() == '' or (line.strip().startswith('#') and len(current_section) > 5):
                    if current_section:
                        sections.append('\n'.join(current_section))
                        current_section = []
                    in_param_section = False
                else:
                    current_section.append(line)
        
        # 添加最后一个章节
        if current_section:
            sections.append('\n'.join(current_section))
        
        return sections
    
    def _parse_parameter_table(self, section: str) -> List[Dict]:
        """解析参数表格"""
        params = []
        lines = section.split('\n')
        
        # 查找表格行
        table_lines = []
        for line in lines:
            if '|' in line and not line.strip().startswith('#'):
                table_lines.append(line)
        
        if len(table_lines) < 2:
            return params
        
        # 解析表头
        header_line = table_lines[0]
        headers = [h.strip() for h in header_line.split('|') if h.strip()]
        
        # 查找表头中的关键列
        name_col = self._find_column(headers, ['名称', 'name', '参数名', '字段名', 'field'])
        type_col = self._find_column(headers, ['类型', 'type', '数据类型', 'data type'])
        required_col = self._find_column(headers, ['必填', 'required', '必须', 'mandatory'])
        desc_col = self._find_column(headers, ['描述', 'description', '说明', 'remark'])
        
        # 解析数据行
        for line in table_lines[2:]:  # 跳过分隔符行
            if not line.strip() or '---' in line:
                continue
            
            cells = [c.strip() for c in line.split('|') if c.strip()]
            
            if len(cells) >= 2:
                param = {
                    'name': cells[name_col] if name_col < len(cells) else '',
                    'type': cells[type_col] if type_col < len(cells) else 'string',
                    'required': '是' in (cells[required_col] if required_col < len(cells) else '否') or 
                               'yes' in (cells[required_col] if required_col < len(cells) else 'no').lower(),
                    'description': cells[desc_col] if desc_col < len(cells) else '',
                }
                
                if param['name']:
                    params.append(param)
        
        return params
    
    def _find_column(self, headers: List[str], keywords: List[str]) -> int:
        """查找包含关键词的列索引"""
        for i, header in enumerate(headers):
            header_lower = header.lower()
            if any(kw in header_lower for kw in keywords):
                return i
        return 0
    
    def _extract_responses(self, content: str) -> List[Dict]:
        """提取响应信息"""
        responses = []
        
        # 查找响应章节
        response_sections = self._find_response_sections(content)
        
        for section in response_sections:
            # 尝试提取JSON响应示例
            json_responses = self._extract_json_examples(section)
            responses.extend(json_responses)
            
            # 提取响应状态码
            status_codes = self._extract_section_status_codes(section)
            responses.extend(status_codes)
        
        return responses
    
    def _find_response_sections(self, content: str) -> List[str]:
        """查找响应相关章节"""
        sections = []
        lines = content.split('\n')
        
        in_response_section = False
        current_section = []
        response_keywords = ['响应', 'response', '返回', 'Response', '返回结果']
        
        for line in lines:
            if any(kw in line.lower() for kw in response_keywords):
                if not in_response_section:
                    in_response_section = True
                    current_section = []
            
            if in_response_section:
                if line.strip() == '' or (line.strip().startswith('#') and len(current_section) > 3):
                    if current_section:
                        sections.append('\n'.join(current_section))
                        current_section = []
                    in_response_section = False
                else:
                    current_section.append(line)
        
        if current_section:
            sections.append('\n'.join(current_section))
        
        return sections
    
    def _extract_json_examples(self, section: str) -> List[Dict]:
        """提取JSON响应示例"""
        responses = []
        
        # 查找JSON代码块
        json_blocks = re.findall(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', section, re.MULTILINE)
        
        for block in json_blocks:
            try:
                # 尝试解析JSON
                json_data = json.loads(block)
                responses.append({
                    'type': 'json',
                    'content': json_data,
                })
            except:
                pass
        
        # 查找内联JSON
        inline_json = re.findall(r'\{[\s\S]*?"[\w]+"[\s\S]*?\}', section)
        for json_str in inline_json[:3]:  # 限制数量
            try:
                json_data = json.loads(json_str)
                responses.append({
                    'type': 'json',
                    'content': json_data,
                })
            except:
                pass
        
        return responses
    
    def _extract_status_codes(self, content: str) -> List[Dict]:
        """提取HTTP状态码"""
        status_codes = []
        
        # 常见的HTTP状态码模式
        status_patterns = [
            (r'200\s*(OK|Success|Created|Success)', '成功'),
            (r'201\s*(Created)', '已创建'),
            (r'204\s*(No Content)', '无内容'),
            (r'400\s*(Bad Request)', '请求错误'),
            (r'401\s*(Unauthorized)', '未授权'),
            (r'403\s*(Forbidden)', '禁止访问'),
            (r'404\s*(Not Found)', '未找到'),
            (r'500\s*(Internal Server Error)', '服务器错误'),
            (r'502\s*(Bad Gateway)', '网关错误'),
            (r'503\s*(Service Unavailable)', '服务不可用'),
        ]
        
        for pattern, desc in status_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                code = re.search(r'\d+', pattern).group()
                status_codes.append({
                    'code': code,
                    'description': desc,
                })
        
        return status_codes
    
    def _extract_section_status_codes(self, section: str) -> List[Dict]:
        """从章节中提取状态码"""
        return self._extract_status_codes(section)
    
    def _build_enhanced_content(
        self, 
        content: str, 
        endpoints: List[APIEndpoint],
        parameters: List[Dict],
        responses: List[Dict]
    ) -> str:
        """构建增强的文档内容"""
        enhanced_parts = [content]
        
        # 添加端点摘要
        if endpoints:
            endpoint_summary = "\n\n## API端点摘要\n"
            for ep in endpoints:
                endpoint_summary += f"- **{ep.method}** `{ep.path}`: {ep.description}\n"
            enhanced_parts.append(endpoint_summary)
        
        # 添加参数摘要
        if parameters:
            param_summary = "\n\n## 参数摘要\n"
            for param in parameters[:20]:  # 限制数量
                required = "必填" if param.get('required') else "可选"
                param_summary += f"- **{param['name']}** ({param.get('type', 'string')}) [{required}]: {param.get('description', '')}\n"
            enhanced_parts.append(param_summary)
        
        return '\n'.join(enhanced_parts)
    
    def _chunk_api_document(self, content: str, metadata: Dict) -> List[Dict]:
        """对API文档进行分块"""
        chunks = []
        
        # 提取端点信息用于分块
        endpoints = metadata.get('api_endpoints', [])
        
        if not endpoints:
            # 如果没有端点信息，使用默认分块
            return self._default_chunking(content, metadata)
        
        # 按端点分块
        for i, endpoint in enumerate(endpoints):
            # 查找该端点在文档中的位置
            endpoint_marker = f"{endpoint['method']} {endpoint['path']}"
            start_idx = content.find(endpoint_marker)
            
            if start_idx == -1:
                continue
            
            # 查找下一个端点的位置
            if i < len(endpoints) - 1:
                next_marker = f"{endpoints[i+1]['method']} {endpoints[i+1]['path']}"
                end_idx = content.find(next_marker)
            else:
                end_idx = len(content)
            
            if end_idx == -1:
                end_idx = len(content)
            
            # 提取该端点的内容
            endpoint_content = content[start_idx:end_idx].strip()
            
            # 进一步按子章节分割（如果内容过长）
            sub_chunks = self._split_by_subsections(endpoint_content, metadata, i)
            chunks.extend(sub_chunks)
        
        return chunks
    
    def _split_by_subsections(self, content: str, metadata: Dict, chunk_index: int) -> List[Dict]:
        """按子章节分割"""
        chunks = []
        
        # 查找子章节
        subsection_headers = re.findall(r'^#{1,3}\s+(.+)$', content, re.MULTILINE)
        
        if len(subsection_headers) <= 1:
            # 内容不长，直接作为一个块
            chunks.append({
                'content': content,
                'metadata': {
                    **metadata,
                    'chunk_index': chunk_index,
                    'chunk_type': 'api_endpoint',
                }
            })
        else:
            # 按子章节分割
            current_pos = 0
            for i, header in enumerate(subsection_headers):
                header_pattern = f"#{{1,3}}\s+{re.escape(header)}"
                match = re.search(header_pattern, content[current_pos:])
                
                if match:
                    if i > 0:
                        # 保存前一个子章节
                        prev_start = current_pos
                        prev_end = current_pos + match.start()
                        subsection_content = content[prev_start:prev_end].strip()
                        
                        if subsection_content:
                            chunks.append({
                                'content': subsection_content,
                                'metadata': {
                                    **metadata,
                                    'chunk_index': f"{chunk_index}_{i-1}",
                                    'chunk_type': 'api_subsection',
                                    'subsection_title': subsection_headers[i-1],
                                }
                            })
                    
                    current_pos = current_pos + match.start() + match.end()
            
            # 添加最后一个子章节
            if current_pos < len(content):
                last_subsection = content[current_pos:].strip()
                if last_subsection:
                    chunks.append({
                        'content': last_subsection,
                        'metadata': {
                            **metadata,
                            'chunk_index': f"{chunk_index}_{len(subsection_headers)-1}",
                            'chunk_type': 'api_subsection',
                            'subsection_title': subsection_headers[-1],
                        }
                    })
        
        return chunks
    
    def _default_chunking(self, content: str, metadata: Dict) -> List[Dict]:
        """默认分块方法"""
        # 使用简单的分段方法
        sections = re.split(r'^#{1,2}\s+', content, flags=re.MULTILINE)
        
        chunks = []
        for i, section in enumerate(sections):
            if section.strip():
                chunks.append({
                    'content': section.strip(),
                    'metadata': {
                        **metadata,
                        'chunk_index': i,
                        'chunk_type': 'api_section',
                    }
                })
        
        return chunks if chunks else [{'content': content, 'metadata': metadata}]


def process_api_document(content: str, metadata: Dict = None) -> Tuple[List[Dict], Dict]:
    """
    处理API文档的便捷函数
    
    Args:
        content: 文档内容
        metadata: 元数据
        
    Returns:
        (文本块列表, 提取的元数据)
    """
    processor = APIDocumentProcessor()
    return processor.process(content, metadata)





