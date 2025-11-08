"""add customer tab_color

Revision ID: add_customer_tab_color
Revises:
Create Date: 2025-11-06

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_customer_tab_color'
down_revision = None
depends_on = None


def upgrade():
    # Add tab_color column to customers table with default white
    op.add_column('customers', sa.Column('tab_color', sa.String(length=7), nullable=True, server_default='#ffffff'))


def downgrade():
    # Remove tab_color column
    op.drop_column('customers', 'tab_color')
