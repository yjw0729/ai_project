# -*- coding: utf-8 -*-
"""
platform_service/db/ - 数据访问层

包含数据库 CRUD 操作类。

Mapper 列表：
- TestCaseMapper: 测试用例 CRUD
- TestExecutionMapper: 测试执行记录 CRUD
- ApiConfigMapper: 接口配置 CRUD
- EnvironmentConfigMapper: 环境配置 CRUD
- DatabaseConfigMapper: 数据库配置 CRUD
- TestSuiteMapper: 测试套件 CRUD
- TestSuiteCaseMapper: 测试套件-用例关联 CRUD
- TestPlanMapper: 测试计划 CRUD
- GlobalVariableMapper: 全局变量 CRUD
- ReviewRecordMapper: 评审记录 CRUD
- ReviewSummaryMapper: 评审汇总 CRUD
- TaskExecutionMapper: 任务执行记录 CRUD
"""

from platform_service.db.test_case_mapper import TestCaseMapper, OptimisticLockError
from platform_service.db.test_execution_mapper import TestExecutionMapper
from platform_service.db.api_config_mapper import ApiConfigMapper
from platform_service.db.environment_config_mapper import EnvironmentConfigMapper
from platform_service.db.database_config_mapper import DatabaseConfigMapper
from platform_service.db.test_suite_mapper import TestSuiteMapper
from platform_service.db.test_suite_case_mapper import TestSuiteCaseMapper
from platform_service.db.test_plan_mapper import TestPlanMapper
from platform_service.db.global_variable_mapper import GlobalVariableMapper
from platform_service.db.review_record_mapper import ReviewRecordMapper
from platform_service.db.review_summary_mapper import ReviewSummaryMapper
from platform_service.db.task_execution_mapper import TaskExecutionMapper

__all__ = [
    "TestCaseMapper",
    "OptimisticLockError",
    "TestExecutionMapper",
    "ApiConfigMapper",
    "EnvironmentConfigMapper",
    "DatabaseConfigMapper",
    "TestSuiteMapper",
    "TestSuiteCaseMapper",
    "TestPlanMapper",
    "GlobalVariableMapper",
    "ReviewRecordMapper",
    "ReviewSummaryMapper",
    "TaskExecutionMapper",
]
