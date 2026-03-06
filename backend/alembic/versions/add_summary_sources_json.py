"""add sources_json to daily_summaries

Revision ID: add_summary_sources_json
Revises: add_customer_sort_order
Create Date: 2026-02-08

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_summary_sources_json'
down_revision = 'add_customer_sort_order'
depends_on = None


def upgrade():
    op.add_column('daily_summaries', sa.Column('sources_json', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('daily_summaries', 'sources_json')
