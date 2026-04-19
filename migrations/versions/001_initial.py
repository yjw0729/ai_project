"""Initial migration - create all crosstest tables

Revision ID: 001_initial
Revises:
Create Date: 2026-04-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- crosstest_test_case ----
    op.create_table(
        'crosstest_test_case',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('case_id', sa.String(length=50), nullable=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.String(length=1000), nullable=True),
        sa.Column('module', sa.String(length=100), nullable=False),
        sa.Column('system', sa.String(length=100), nullable=True),
        sa.Column('priority', sa.Enum('P0', 'P1', 'P2', 'P3', name='testcase_priority'), nullable=False),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('api_config_id', sa.Integer(), nullable=True),
        sa.Column('preconditions', sa.Text(), nullable=True),
        sa.Column('test_steps', sa.JSON(), nullable=False),
        sa.Column('setup_scripts', sa.JSON(), nullable=True),
        sa.Column('teardown_scripts', sa.JSON(), nullable=True),
        sa.Column('expected_results', sa.JSON(), nullable=True),
        sa.Column('extract_fields', sa.JSON(), nullable=True),
        sa.Column('test_data', sa.JSON(), nullable=True),
        sa.Column('variables', sa.JSON(), nullable=True),
        sa.Column('max_retry_times', sa.Integer(), nullable=True),
        sa.Column('timeout', sa.Integer(), nullable=True),
        sa.Column('status', sa.Enum('draft', 'active', 'inactive', 'deprecated', name='testcase_status'), nullable=False),
        sa.Column('case_status', sa.Enum('enabled', 'disabled', name='testcase_casestatus'), nullable=False),
        sa.Column('last_execution_status', sa.Enum('not_run', 'success', 'failed', name='execution_status'), nullable=False),
        sa.Column('last_execution_time', sa.DateTime(), nullable=True),
        sa.Column('last_execution_result', sa.JSON(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=True),
        sa.Column('creator', sa.String(length=50), nullable=False),
        sa.Column('reviewer', sa.String(length=50), nullable=True),
        sa.Column('review_status', sa.Enum('pending', 'approved', 'rejected', name='review_status'), nullable=True),
        sa.Column('review_comment', sa.Text(), nullable=True),
        sa.Column('created_time', sa.DateTime(), nullable=True),
        sa.Column('updated_time', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('case_id'),
    )

    # ---- crosstest_api_config ----
    op.create_table(
        'crosstest_api_config',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('module', sa.String(length=100), nullable=False),
        sa.Column('api_path', sa.String(length=500), nullable=False),
        sa.Column('method', sa.Enum('GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS', name='http_method'), nullable=False),
        sa.Column('request_type', sa.Enum('json', 'form', 'file', name='request_type'), nullable=False),
        sa.Column('headers', sa.JSON(), nullable=True),
        sa.Column('default_params', sa.JSON(), nullable=True),
        sa.Column('request_body_template', sa.JSON(), nullable=True),
        sa.Column('is_encryption', sa.Boolean(), nullable=True),
        sa.Column('encryption_config', sa.JSON(), nullable=True),
        sa.Column('expected_response', sa.JSON(), nullable=True),
        sa.Column('timeout', sa.Integer(), nullable=True),
        sa.Column('retry_times', sa.Integer(), nullable=True),
        sa.Column('is_deprecated', sa.Boolean(), nullable=True),
        sa.Column('tag', sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # ---- crosstest_environment_config ----
    op.create_table(
        'crosstest_environment_config',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('base_url', sa.String(length=500), nullable=False),
        sa.Column('env_type', sa.Enum('dev', 'test', 'staging', 'prod', name='env_type'), nullable=False),
        sa.Column('database_config_id', sa.Integer(), nullable=True),
        sa.Column('headers', sa.JSON(), nullable=True),
        sa.Column('variables', sa.JSON(), nullable=True),
        sa.Column('timeout', sa.Integer(), nullable=True),
        sa.Column('is_encryption', sa.Boolean(), nullable=True),
        sa.Column('encryption_config', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_by', sa.String(length=50), nullable=True),
        sa.Column('created_time', sa.DateTime(), nullable=True),
        sa.Column('updated_by', sa.String(length=50), nullable=True),
        sa.Column('updated_time', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )

    # ---- crosstest_test_suite ----
    op.create_table(
        'crosstest_test_suite',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.String(length=1000), nullable=True),
        sa.Column('suite_type', sa.Enum('smoke', 'regression', 'function', 'performance', 'custom', name='suite_type'), nullable=False),
        sa.Column('module', sa.String(length=100), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('last_execution_status', sa.Enum('not_run', 'running', 'passed', 'failed', 'stopped', name='suite_exec_status'), nullable=False),
        sa.Column('last_execution_time', sa.DateTime(), nullable=True),
        sa.Column('last_execution_id', sa.String(length=50), nullable=True),
        sa.Column('total_executions', sa.Integer(), nullable=False),
        sa.Column('success_rate', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('case_default_config', sa.JSON(), nullable=True),
        sa.Column('status', sa.Enum('active', 'inactive', name='suite_status'), nullable=False),
        sa.Column('creator', sa.String(length=50), nullable=False),
        sa.Column('created_time', sa.DateTime(), nullable=True),
        sa.Column('updated_time', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )

    # ---- crosstest_test_suite_case ----
    op.create_table(
        'crosstest_test_suite_case',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('suite_id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=True),
        sa.Column('case_id_str', sa.String(length=50), nullable=True),
        sa.Column('execution_order', sa.Integer(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=True),
        sa.Column('url', sa.String(length=500), nullable=True),
        sa.Column('request_headers', sa.JSON(), nullable=True),
        sa.Column('request_params', sa.JSON(), nullable=True),
        sa.Column('request_body', sa.JSON(), nullable=True),
        sa.Column('timeout', sa.Integer(), nullable=True),
        sa.Column('assertions', sa.JSON(), nullable=True),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('preconditions', sa.Text(), nullable=True),
        sa.Column('test_steps', sa.JSON(), nullable=True),
        sa.Column('test_data', sa.JSON(), nullable=True),
        sa.Column('created_time', sa.DateTime(), nullable=True),
        sa.Column('updated_time', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['suite_id'], ['crosstest_test_suite.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['case_id'], ['crosstest_test_case.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # ---- crosstest_global_variable ----
    op.create_table(
        'crosstest_global_variable',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('variable_type', sa.Enum('static', 'dynamic', 'encrypted', name='var_type'), nullable=False),
        sa.Column('scope', sa.Enum('global', 'environment', 'module', name='var_scope'), nullable=False),
        sa.Column('scope_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_by', sa.String(length=50), nullable=True),
        sa.Column('created_time', sa.DateTime(), nullable=True),
        sa.Column('updated_by', sa.String(length=50), nullable=True),
        sa.Column('updated_time', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # ---- crosstest_task_execution ----
    op.create_table(
        'crosstest_task_execution',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.String(length=100), nullable=False),
        sa.Column('user_id', sa.String(length=50), nullable=False),
        sa.Column('task_type', sa.String(length=50), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('error_code', sa.String(length=50), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True),
        sa.Column('max_retries', sa.Integer(), nullable=True),
        sa.Column('trace_id', sa.String(length=100), nullable=True),
        sa.Column('created_time', sa.DateTime(), nullable=True),
        sa.Column('queued_time', sa.DateTime(), nullable=True),
        sa.Column('started_time', sa.DateTime(), nullable=True),
        sa.Column('finished_time', sa.DateTime(), nullable=True),
        sa.Column('progress', sa.String(length=50), nullable=True),
        sa.Column('created_by', sa.String(length=50), nullable=True),
        sa.Column('updated_by', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('task_id'),
    )

    # ---- assertion_configs (SQLite, keep for common/models/assertion.py) ----
    op.create_table(
        'assertion_configs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('interface_id', sa.Integer(), nullable=False),
        sa.Column('version', sa.String(length=20), nullable=False),
        sa.Column('assertions', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('assertion_configs')
    op.drop_table('crosstest_task_execution')
    op.drop_table('crosstest_global_variable')
    op.drop_table('crosstest_test_suite_case')
    op.drop_table('crosstest_test_suite')
    op.drop_table('crosstest_environment_config')
    op.drop_table('crosstest_api_config')
    op.drop_table('crosstest_test_case')
