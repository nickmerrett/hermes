"""add customer sort_order

Revision ID: add_customer_sort_order
Revises: add_cascade_delete_fk
Create Date: 2026-01-28

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_customer_sort_order'
down_revision = 'add_cascade_delete_fk'
depends_on = None


def upgrade():
    op.add_column('customers', sa.Column('sort_order', sa.Integer(), nullable=True, server_default='0'))


def downgrade():
    op.drop_column('customers', 'sort_order')
