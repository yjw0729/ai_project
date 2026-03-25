# -*- coding: utf-8 -*-
"""
公共图片分析模块

提供统一的图片OCR和流程图分析功能，供全项目复用。

主要功能：
- 从图片文件识别文字内容
- 分析流程图/泳道图，提取系统组件、交互关系、业务流程等

使用方法：
    from common.image_analysis.image_analyzer import ImageAnalyzer, analyze_image

    # 方式1：使用便捷函数
    result = analyze_image(image_bytes)
    result = analyze_image(image_path="path/to/image.png")

    # 方式2：使用类实例
    analyzer = ImageAnalyzer()
    result = analyzer.analyze_flowchart(image_bytes)
    result = analyzer.extract_text(image_bytes)
"""

import base64
import logging
from typing import Optional, Dict, Any, Union
from pathlib import Path

logger = logging.getLogger(__name__)


class ImageAnalyzer:
    """
    图片分析器

    使用千问3多模态模型进行图片OCR和流程图分析。
    提取最详细的结构化信息，包括：
    - 系统组件和参与方
    - 交互顺序和调用关系
    - 业务流程步骤（正向/异常）
    - 数据流向
    - 分支、循环、并行等特殊逻辑
    """

    # 默认模型
    DEFAULT_MODEL = "qwen3.5-plus"

    # 流程图分析提示词（最详细的结构化提示词）
    FLOWCHART_ANALYSIS_PROMPT = """请分析这张系统交互流程图或泳道图，提取以下信息：
1. 涉及的系统和组件（有哪些参与方）
2. 各系统之间的交互顺序和调用关系
3. 图中所标明的的业务流程步骤包括正向流程和异常的流程，
4. 关键的数据流向
5. 是否有分支、循环、并行等特殊逻辑，如果存在那么将这些逻辑查找狐出来

使用资深产品设计工程师的角度，用结构化的方式描述这个图内的业务流程，
如果图片不包含流程图信息，请说明"未识别到流程图"。"""

    # 通用OCR提示词
    GENERAL_OCR_PROMPT = """请识别图片中的所有文字内容，保持原有格式。如果是流程图或表格，请描述其结构。"""

    def __init__(self, model: str = None):
        """
        初始化图片分析器

        Args:
            model: 使用的模型，默认 qwen3.5-plus
        """
        self.model = model or self.DEFAULT_MODEL

    def _get_api_key(self) -> Optional[str]:
        """获取API Key"""
        import os
        return os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("OPENAI_API_KEY")

    def _call_multimodal_model(
        self,
        image_bytes: bytes,
        prompt: str,
        image_format: str = "png"
    ) -> Optional[str]:
        """
        调用多模态模型

        Args:
            image_bytes: 图片二进制数据
            prompt: 提示词
            image_format: 图片格式，默认 png

        Returns:
            模型返回的文本内容，失败返回 None
        """
        try:
            import dashscope
            from dashscope import MultiModalConversation

            api_key = self._get_api_key()
            if not api_key:
                logger.warning("未设置 DASHSCOPE_API_KEY 环境变量")
                return None

            dashscope.api_key = api_key

            # 将图片转为 base64
            img_base64 = base64.b64encode(image_bytes).decode('utf-8')

            # 构建消息
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "image": f"data:image/{image_format};base64,{img_base64}"
                        },
                        {
                            "text": prompt
                        }
                    ]
                }
            ]

            logger.debug(f"开始调用多模态模型 {self.model}...")

            response = MultiModalConversation.call(
                model=self.model,
                messages=messages
            )

            if response.status_code == 200:
                result_content = response.output.choices[0].message.content
                analysis_text = ""
                for item in result_content:
                    if 'text' in item:
                        analysis_text += item['text']
                return analysis_text
            else:
                logger.warning(f"模型调用失败: {response.code} - {response.message}")
                return None

        except Exception as e:
            logger.error(f"调用多模态模型失败: {e}", exc_info=True)
            return None

    def analyze_flowchart(
        self,
        image_bytes: bytes = None,
        image_path: str = None,
        image_format: str = "png"
    ) -> Dict[str, Any]:
        """
        分析流程图/泳道图

        提取系统组件、交互关系、业务流程、数据流向、分支逻辑等。

        Args:
            image_bytes: 图片二进制数据
            image_path: 图片文件路径（二选一）
            image_format: 图片格式，默认 png

        Returns:
            {
                "success": bool,
                "analysis": str,  # 分析结果文本
                "error": str  # 失败时的错误信息
            }
        """
        # 加载图片
        if image_path:
            try:
                with open(image_path, "rb") as f:
                    image_bytes = f.read()
            except Exception as e:
                logger.error(f"读取图片文件失败: {e}")
                return {
                    "success": False,
                    "error": f"读取图片文件失败: {e}",
                    "analysis": ""
                }

        if not image_bytes:
            return {
                "success": False,
                "error": "未提供图片数据",
                "analysis": ""
            }

        logger.info(f"开始分析流程图图片...")

        result = self._call_multimodal_model(
            image_bytes=image_bytes,
            prompt=self.FLOWCHART_ANALYSIS_PROMPT,
            image_format=image_format
        )

        if result is not None:
            logger.info(f"流程图分析完成，结果长度: {len(result)}")
            return {
                "success": True,
                "analysis": result,
                "error": ""
            }
        else:
            return {
                "success": False,
                "error": "模型调用失败",
                "analysis": ""
            }

    def extract_text(
        self,
        image_bytes: bytes = None,
        image_path: str = None,
        image_format: str = "png"
    ) -> Dict[str, Any]:
        """
        提取图片中的文字（通用OCR）

        使用通用OCR提示词识别图片文字。

        Args:
            image_bytes: 图片二进制数据
            image_path: 图片文件路径（二选一）
            image_format: 图片格式，默认 png

        Returns:
            {
                "success": bool,
                "text": str,  # 识别出的文本
                "error": str  # 失败时的错误信息
            }
        """
        # 加载图片
        if image_path:
            try:
                with open(image_path, "rb") as f:
                    image_bytes = f.read()
            except Exception as e:
                logger.error(f"读取图片文件失败: {e}")
                return {
                    "success": False,
                    "error": f"读取图片文件失败: {e}",
                    "text": ""
                }

        if not image_bytes:
            return {
                "success": False,
                "error": "未提供图片数据",
                "text": ""
            }

        logger.info(f"开始识别图片文字...")

        result = self._call_multimodal_model(
            image_bytes=image_bytes,
            prompt=self.GENERAL_OCR_PROMPT,
            image_format=image_format
        )

        if result is not None:
            logger.info(f"文字识别完成，结果长度: {len(result)}")
            return {
                "success": True,
                "text": result,
                "error": ""
            }
        else:
            return {
                "success": False,
                "error": "模型调用失败",
                "text": ""
            }

    def analyze(
        self,
        image_bytes: bytes = None,
        image_path: str = None,
        mode: str = "flowchart",
        image_format: str = "png"
    ) -> Dict[str, Any]:
        """
        通用分析接口

        Args:
            image_bytes: 图片二进制数据
            image_path: 图片文件路径（二选一）
            mode: 分析模式，"flowchart" 或 "ocr"
            image_format: 图片格式

        Returns:
            分析结果字典
        """
        if mode == "flowchart":
            return self.analyze_flowchart(image_bytes, image_path, image_format)
        elif mode == "ocr":
            return self.extract_text(image_bytes, image_path, image_format)
        else:
            return {
                "success": False,
                "error": f"未知的分析模式: {mode}",
                "analysis": "" if mode == "flowchart" else ""
            }


# ========== 便捷函数 ==========

def analyze_image(
    image_bytes: bytes = None,
    image_path: str = None,
    mode: str = "flowchart",
    image_format: str = "png"
) -> Dict[str, Any]:
    """
    便捷函数：分析图片

    Args:
        image_bytes: 图片二进制数据
        image_path: 图片文件路径（二选一）
        mode: 分析模式，"flowchart" 或 "ocr"
        image_format: 图片格式

    Returns:
        分析结果字典
    """
    analyzer = ImageAnalyzer()
    return analyzer.analyze(image_bytes, image_path, mode, image_format)


def analyze_flowchart(
    image_bytes: bytes = None,
    image_path: str = None,
    image_format: str = "png"
) -> Dict[str, Any]:
    """
    便捷函数：分析流程图

    Args:
        image_bytes: 图片二进制数据
        image_path: 图片文件路径（二选一）
        image_format: 图片格式

    Returns:
        分析结果字典
    """
    analyzer = ImageAnalyzer()
    return analyzer.analyze_flowchart(image_bytes, image_path, image_format)


def extract_image_text(
    image_bytes: bytes = None,
    image_path: str = None,
    image_format: str = "png"
) -> Dict[str, Any]:
    """
    便捷函数：提取图片文字

    Args:
        image_bytes: 图片二进制数据
        image_path: 图片文件路径（二选一）
        image_format: 图片格式

    Returns:
        识别结果字典
    """
    analyzer = ImageAnalyzer()
    return analyzer.extract_text(image_bytes, image_path, image_format)


# ========== 保持向后兼容的别名 ==========

def analyze_flowchart_image(image_bytes: bytes, image_index: int = 0) -> dict:
    """
    向后兼容函数：分析流程图图片

    此函数签名与 http_test_case_generate.py 中的原有函数保持一致，
    内部调用新的 ImageAnalyzer 类。

    Args:
        image_bytes: 图片二进制数据
        image_index: 图片索引（仅用于兼容，不影响分析）

    Returns:
        {
            "success": bool,
            "analysis": str,
            "image_index": int,
            "error": str
        }
    """
    analyzer = ImageAnalyzer()
    result = analyzer.analyze_flowchart(image_bytes=image_bytes)

    return {
        "success": result["success"],
        "analysis": result.get("analysis", ""),
        "image_index": image_index,
        "error": result.get("error", "")
    }


__all__ = [
    "ImageAnalyzer",
    "analyze_image",
    "analyze_flowchart",
    "extract_image_text",
    "analyze_flowchart_image",  # 向后兼容
]
