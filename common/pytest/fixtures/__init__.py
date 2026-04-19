"""
pytest fixtures 封装模块。

该模块提供了分类组织的 pytest fixtures，包括：
- api_client: API 客户端相关 fixtures
- auth: 认证相关 fixtures
- database: 数据库相关 fixtures
- cleanup: 清理相关 fixtures

使用示例：
    from fixtures import api_client, auth, database, cleanup

    def test_example(api_client, auth_token, db_session, cleanup_actions):
        # 测试代码
        pass
"""

__version__ = "1.0.0"
__all__ = ["api_client", "auth", "database", "cleanup"]