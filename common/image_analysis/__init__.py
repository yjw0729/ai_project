# -*- coding: utf-8 -*-
"""
公共图片分析模块

提供统一的图片OCR和流程图分析功能
"""

from common.image_analysis.image_analyzer import (
    ImageAnalyzer,
    analyze_image,
    analyze_flowchart,
    extract_image_text,
    analyze_flowchart_image,  # 向后兼容
)

__all__ = [
    "ImageAnalyzer",
    "analyze_image",
    "analyze_flowchart",
    "extract_image_text",
    "analyze_flowchart_image",
]
