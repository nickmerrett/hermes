#!/usr/bin/env python3
"""
Migration: Allow same URL to be collected for multiple customers

Changes:
1. Remove unique constraint on intelligence_items.url
2. Add composite unique constraint on (customer_id, url)

This allows the same article to be relevant to multiple customers.
"""

from alembic import op
import sqlalchemy as sa


def upgrade():
    """Apply migration"""
    # SQLite doesn't support dropping constraints directly, so we need to recreate the table

    # Create new table with correct constraints
    op.create_table(
        'intelligence_items_new',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=True),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('url', sa.String(length=2048), nullable=True),
        sa.Column('published_date', sa.DateTime(), nullable=True),
        sa.Column('collected_date', sa.DateTime(), nullable=True),
        sa.Column('raw_data', sa.JSON(), nullable=True),
        sa.Column('cluster_id', sa.String(length=36), nullable=True),
        sa.Column('is_cluster_primary', sa.Boolean(), nullable=True),
        sa.Column('source_tier', sa.String(length=20), nullable=True),
        sa.Column('cluster_member_count', sa.Integer(), nullable=True),
        sa.Column('ignored', sa.Boolean(), nullable=True),
        sa.Column('ignored_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id']),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id']),
        sa.UniqueConstraint('customer_id', 'url', name='uix_customer_url')  # New composite constraint
    )

    # Copy data from old table to new
    op.execute("""
        INSERT INTO intelligence_items_new
        SELECT * FROM intelligence_items
    """)

    # Drop old table
    op.drop_table('intelligence_items')

    # Rename new table
    op.rename_table('intelligence_items_new', 'intelligence_items')

    # Recreate indexes
    op.create_index('ix_intelligence_items_customer_id', 'intelligence_items', ['customer_id'])
    op.create_index('ix_intelligence_items_source_type', 'intelligence_items', ['source_type'])
    op.create_index('ix_intelligence_items_url', 'intelligence_items', ['url'])
    op.create_index('ix_intelligence_items_published_date', 'intelligence_items', ['published_date'])
    op.create_index('ix_intelligence_items_collected_date', 'intelligence_items', ['collected_date'])
    op.create_index('ix_intelligence_items_cluster_id', 'intelligence_items', ['cluster_id'])
    op.create_index('ix_intelligence_items_is_cluster_primary', 'intelligence_items', ['is_cluster_primary'])
    op.create_index('ix_intelligence_items_ignored', 'intelligence_items', ['ignored'])


def downgrade():
    """Revert migration"""
    # Revert back to globally unique URL
    op.create_table(
        'intelligence_items_old',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=True),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('url', sa.String(length=2048), nullable=True),
        sa.Column('published_date', sa.DateTime(), nullable=True),
        sa.Column('collected_date', sa.DateTime(), nullable=True),
        sa.Column('raw_data', sa.JSON(), nullable=True),
        sa.Column('cluster_id', sa.String(length=36), nullable=True),
        sa.Column('is_cluster_primary', sa.Boolean(), nullable=True),
        sa.Column('source_tier', sa.String(length=20), nullable=True),
        sa.Column('cluster_member_count', sa.Integer(), nullable=True),
        sa.Column('ignored', sa.Boolean(), nullable=True),
        sa.Column('ignored_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id']),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id']),
        sa.UniqueConstraint('url', name='uq_url')  # Globally unique URL
    )

    # Copy data (this may fail if there are duplicate URLs across customers)
    op.execute("""
        INSERT INTO intelligence_items_old
        SELECT * FROM intelligence_items
        WHERE id IN (
            SELECT MIN(id) FROM intelligence_items GROUP BY url
        )
    """)

    op.drop_table('intelligence_items')
    op.rename_table('intelligence_items_old', 'intelligence_items')
