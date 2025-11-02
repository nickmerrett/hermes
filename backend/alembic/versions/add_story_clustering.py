"""Add story clustering fields

Revision ID: add_story_clustering
Revises:
Create Date: 2025-10-31

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_story_clustering'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add clustering fields to intelligence_items table
    op.add_column('intelligence_items', sa.Column('cluster_id', sa.String(length=36), nullable=True))
    op.add_column('intelligence_items', sa.Column('is_cluster_primary', sa.Boolean(), nullable=True, server_default='0'))
    op.add_column('intelligence_items', sa.Column('source_tier', sa.String(length=20), nullable=True))
    op.add_column('intelligence_items', sa.Column('cluster_member_count', sa.Integer(), nullable=True, server_default='1'))

    # Add indexes for performance
    op.create_index('ix_intelligence_items_cluster_id', 'intelligence_items', ['cluster_id'])
    op.create_index('ix_intelligence_items_is_cluster_primary', 'intelligence_items', ['is_cluster_primary'])


def downgrade():
    # Remove indexes
    op.drop_index('ix_intelligence_items_is_cluster_primary', table_name='intelligence_items')
    op.drop_index('ix_intelligence_items_cluster_id', table_name='intelligence_items')

    # Remove columns
    op.drop_column('intelligence_items', 'cluster_member_count')
    op.drop_column('intelligence_items', 'source_tier')
    op.drop_column('intelligence_items', 'is_cluster_primary')
    op.drop_column('intelligence_items', 'cluster_id')
