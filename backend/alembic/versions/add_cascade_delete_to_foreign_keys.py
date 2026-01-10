"""add cascade delete to foreign keys

Revision ID: add_cascade_delete_fk
Revises: add_customer_tab_color
Create Date: 2025-12-30

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_cascade_delete_fk'
down_revision = 'add_customer_tab_color'
depends_on = None


def upgrade():
    """Add CASCADE DELETE to all foreign key constraints"""

    # Get bind for executing raw SQL
    bind = op.get_bind()

    # Drop and recreate foreign keys with ON DELETE CASCADE
    # Note: SQLite doesn't support DROP CONSTRAINT, so we need to check the database type

    if bind.dialect.name == 'sqlite':
        # For SQLite, we need to recreate tables (more complex, handled by dropping and recreating)
        # SQLite foreign key constraints can be managed through PRAGMA foreign_keys
        pass
    else:
        # For PostgreSQL/MySQL, drop and recreate constraints

        # Sources table - customer_id
        op.drop_constraint('sources_customer_id_fkey', 'sources', type_='foreignkey')
        op.create_foreign_key('sources_customer_id_fkey', 'sources', 'customers', ['customer_id'], ['id'], ondelete='CASCADE')

        # IntelligenceItems table - customer_id and source_id
        op.drop_constraint('intelligence_items_customer_id_fkey', 'intelligence_items', type_='foreignkey')
        op.create_foreign_key('intelligence_items_customer_id_fkey', 'intelligence_items', 'customers', ['customer_id'], ['id'], ondelete='CASCADE')

        op.drop_constraint('intelligence_items_source_id_fkey', 'intelligence_items', type_='foreignkey')
        op.create_foreign_key('intelligence_items_source_id_fkey', 'intelligence_items', 'sources', ['source_id'], ['id'], ondelete='CASCADE')

        # ProcessedIntelligence table - item_id
        op.drop_constraint('processed_intelligence_item_id_fkey', 'processed_intelligence', type_='foreignkey')
        op.create_foreign_key('processed_intelligence_item_id_fkey', 'processed_intelligence', 'intelligence_items', ['item_id'], ['id'], ondelete='CASCADE')

        # CollectionJob table - customer_id and source_id
        op.drop_constraint('collection_jobs_customer_id_fkey', 'collection_jobs', type_='foreignkey')
        op.create_foreign_key('collection_jobs_customer_id_fkey', 'collection_jobs', 'customers', ['customer_id'], ['id'], ondelete='CASCADE')

        op.drop_constraint('collection_jobs_source_id_fkey', 'collection_jobs', type_='foreignkey')
        op.create_foreign_key('collection_jobs_source_id_fkey', 'collection_jobs', 'sources', ['source_id'], ['id'], ondelete='CASCADE')

        # DailySummary table - customer_id
        op.drop_constraint('daily_summaries_customer_id_fkey', 'daily_summaries', type_='foreignkey')
        op.create_foreign_key('daily_summaries_customer_id_fkey', 'daily_summaries', 'customers', ['customer_id'], ['id'], ondelete='CASCADE')

        # CollectionStatus table - customer_id
        op.drop_constraint('collection_status_customer_id_fkey', 'collection_status', type_='foreignkey')
        op.create_foreign_key('collection_status_customer_id_fkey', 'collection_status', 'customers', ['customer_id'], ['id'], ondelete='CASCADE')


def downgrade():
    """Remove CASCADE DELETE from foreign key constraints"""

    bind = op.get_bind()

    if bind.dialect.name == 'sqlite':
        pass
    else:
        # Recreate foreign keys without ondelete

        # Sources table
        op.drop_constraint('sources_customer_id_fkey', 'sources', type_='foreignkey')
        op.create_foreign_key('sources_customer_id_fkey', 'sources', 'customers', ['customer_id'], ['id'])

        # IntelligenceItems table
        op.drop_constraint('intelligence_items_customer_id_fkey', 'intelligence_items', type_='foreignkey')
        op.create_foreign_key('intelligence_items_customer_id_fkey', 'intelligence_items', 'customers', ['customer_id'], ['id'])

        op.drop_constraint('intelligence_items_source_id_fkey', 'intelligence_items', type_='foreignkey')
        op.create_foreign_key('intelligence_items_source_id_fkey', 'intelligence_items', 'sources', ['source_id'], ['id'])

        # ProcessedIntelligence table
        op.drop_constraint('processed_intelligence_item_id_fkey', 'processed_intelligence', type_='foreignkey')
        op.create_foreign_key('processed_intelligence_item_id_fkey', 'processed_intelligence', 'intelligence_items', ['item_id'], ['id'])

        # CollectionJob table
        op.drop_constraint('collection_jobs_customer_id_fkey', 'collection_jobs', type_='foreignkey')
        op.create_foreign_key('collection_jobs_customer_id_fkey', 'collection_jobs', 'customers', ['customer_id'], ['id'])

        op.drop_constraint('collection_jobs_source_id_fkey', 'collection_jobs', type_='foreignkey')
        op.create_foreign_key('collection_jobs_source_id_fkey', 'collection_jobs', 'sources', ['source_id'], ['id'])

        # DailySummary table
        op.drop_constraint('daily_summaries_customer_id_fkey', 'daily_summaries', type_='foreignkey')
        op.create_foreign_key('daily_summaries_customer_id_fkey', 'daily_summaries', 'customers', ['customer_id'], ['id'])

        # CollectionStatus table
        op.drop_constraint('collection_status_customer_id_fkey', 'collection_status', type_='foreignkey')
        op.create_foreign_key('collection_status_customer_id_fkey', 'collection_status', 'customers', ['customer_id'], ['id'])
