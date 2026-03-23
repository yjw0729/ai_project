# -*- coding: utf-8 -*-
"""
platform_service/models/ - 实体层

包含数据表映射实体类，定义数据库表的结构。

实体列表：
- TestCase: 测试用例
- TestExecution: 测试执行记录
- ApiConfig: 接口配置
- EnvironmentConfig: 环境配置
- DatabaseConfig: 数据库配置
- TestSuite: 测试套件
- TestSuiteCase: 测试套件-用例关联
- TestPlan: 测试计划
- GlobalVariable: 全局变量
- ReviewRecord: 评审记录
- ReviewSummary: 评审汇总
- TaskExecution: 任务执行记录
"""

from platform_service.models.test_case import TestCase
from platform_service.models.test_execution import TestExecution
from platform_service.models.api_config import ApiConfig
from platform_service.models.environment_config import EnvironmentConfig
from platform_service.models.database_config import DatabaseConfig
from platform_service.models.test_suite import TestSuite
from platform_service.models.test_suite_case import TestSuiteCase
from platform_service.models.test_plan import TestPlan
from platform_service.models.global_variable import GlobalVariable
from platform_service.models.review_record import ReviewRecord
from platform_service.models.review_summary import ReviewSummary
from platform_service.models.task_execution import TaskExecution

__all__ = [
    "TestCase",
    "TestExecution",
    "ApiConfig",
    "EnvironmentConfig",
    "DatabaseConfig",
    "TestSuite",
    "TestSuiteCase",
    "TestPlan",
    "GlobalVariable",
    "ReviewRecord",
    "ReviewSummary",
    "TaskExecution",
]
