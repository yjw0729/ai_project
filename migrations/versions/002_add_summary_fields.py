"""Add page_count, flow_chart_count, project_background, business_summary to crosstest_review_summary

Revision ID: 002_add_summary_fields
Revises: 001_initial
Create Date: 2026-04-18
"""
from alembic import op
import sqlalchemy as sa

revision = '002_add_summary_fields'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('crosstest_review_summary',
                  sa.Column('page_count', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('crosstest_review_summary',
                  sa.Column('flow_chart_count', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('crosstest_review_summary',
                  sa.Column('project_background', sa.Text(), nullable=True))
    op.add_column('crosstest_review_summary',
                  sa.Column('business_summary', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('crosstest_review_summary', 'business_summary')
    op.drop_column('crosstest_review_summary', 'project_background')
    op.drop_column('crosstest_review_summary', 'flow_chart_count')
    op.drop_column('crosstest_review_summary', 'page_count')
