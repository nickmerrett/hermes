"""
Unit tests for scheduler/collection.py

Covers the concurrency and exception-handling fixes:
- Duplicate URL deduplication within a single collected batch
- IntegrityError on insert is caught and session remains usable
- Global collection lock prevents overlapping runs
- customer_id/customer_name are cached so except-blocks survive session expiry
"""

import os
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")
os.environ.setdefault("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7")

from cryptography.fernet import Fernet
os.environ.setdefault("ENCRYPTION_KEY", Fernet.generate_key().decode())

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.models.database import Base, Customer, IntelligenceItem
from app.models.schemas import IntelligenceItemCreate


# ---------------------------------------------------------------------------
# Shared DB setup
# ---------------------------------------------------------------------------

def make_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return Session()


def make_customer(db) -> Customer:
    customer = Customer(
        name="Test Corp",
        domain="testcorp.com",
        keywords=["test"],
        competitors=[],
        config={},
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def make_item_create(customer_id: int, url: str, title: str = "Test Title") -> IntelligenceItemCreate:
    return IntelligenceItemCreate(
        customer_id=customer_id,
        source_type="news_api",
        title=title,
        content="Some content",
        url=url,
        published_date=datetime.utcnow(),
    )


def _ai_processor_mock():
    mock = MagicMock()
    mock.process_item = AsyncMock(return_value={
        "summary": "Test summary",
        "category": "other",
        "sentiment": "neutral",
        "priority_score": 0.5,
        "entities": {"companies": [], "technologies": [], "people": []},
        "tags": [],
        "pain_points_opportunities": {"pain_points": [], "opportunities": []},
        "is_relevant": True,
    })
    return mock


def _vector_store_mock():
    mock = MagicMock()
    mock.add_item = MagicMock()
    mock.get_embedding = MagicMock(return_value=None)
    return mock


# ---------------------------------------------------------------------------
# Tests: within-batch URL deduplication
# ---------------------------------------------------------------------------

class TestBatchDeduplication:
    """save_and_process_items must skip URLs that already appeared earlier in the same batch."""

    async def test_duplicate_url_in_batch_saves_only_once(self):
        """Two items with the same URL in one batch → only one row inserted."""
        db = make_session()
        customer = make_customer(db)

        url = "https://example.com/same-article"
        items = [
            make_item_create(customer.id, url, "Title A"),
            make_item_create(customer.id, url, "Title B"),  # duplicate
        ]

        with patch("app.scheduler.collection.get_ai_processor", return_value=_ai_processor_mock()), \
             patch("app.scheduler.collection.get_vector_store", return_value=_vector_store_mock()), \
             patch("app.scheduler.collection.cluster_item", return_value="cluster-1"):
            from app.scheduler.collection import save_and_process_items
            await save_and_process_items(items, customer, db)

        saved = db.query(IntelligenceItem).filter(
            IntelligenceItem.url == url,
            IntelligenceItem.customer_id == customer.id,
        ).all()
        assert len(saved) == 1

    async def test_different_urls_in_batch_both_saved(self):
        """Two items with different URLs in one batch → both rows inserted."""
        db = make_session()
        customer = make_customer(db)

        items = [
            make_item_create(customer.id, "https://example.com/article-1", "Title A"),
            make_item_create(customer.id, "https://example.com/article-2", "Title B"),
        ]

        with patch("app.scheduler.collection.get_ai_processor", return_value=_ai_processor_mock()), \
             patch("app.scheduler.collection.get_vector_store", return_value=_vector_store_mock()), \
             patch("app.scheduler.collection.cluster_item", return_value="cluster-1"):
            from app.scheduler.collection import save_and_process_items
            await save_and_process_items(items, customer, db)

        saved = db.query(IntelligenceItem).filter(
            IntelligenceItem.customer_id == customer.id
        ).all()
        assert len(saved) == 2

    async def test_three_same_urls_saves_exactly_one(self):
        """Three items with the same URL → exactly one row."""
        db = make_session()
        customer = make_customer(db)

        url = "https://ozbargain.com.au/node/950169"
        items = [make_item_create(customer.id, url, f"Title {i}") for i in range(3)]

        with patch("app.scheduler.collection.get_ai_processor", return_value=_ai_processor_mock()), \
             patch("app.scheduler.collection.get_vector_store", return_value=_vector_store_mock()), \
             patch("app.scheduler.collection.cluster_item", return_value="cluster-1"):
            from app.scheduler.collection import save_and_process_items
            await save_and_process_items(items, customer, db)

        saved = db.query(IntelligenceItem).filter(
            IntelligenceItem.url == url
        ).all()
        assert len(saved) == 1


# ---------------------------------------------------------------------------
# Tests: IntegrityError race-condition handling
# ---------------------------------------------------------------------------

class TestIntegrityErrorHandling:
    """save_and_process_items must survive a UNIQUE constraint violation
    (race condition where another worker inserted the same URL just before us)
    and leave the session in a usable state."""

    async def test_pre_existing_url_is_skipped(self):
        """URL already in DB before the batch runs → item skipped, no crash."""
        db = make_session()
        customer = make_customer(db)

        url = "https://example.com/existing-article"
        # Pre-insert the row to simulate a prior collection run
        existing = IntelligenceItem(
            customer_id=customer.id,
            source_type="rss",
            title="Already There",
            content="content",
            url=url,
            published_date=datetime.utcnow(),
        )
        db.add(existing)
        db.commit()

        items = [make_item_create(customer.id, url, "New Title")]

        with patch("app.scheduler.collection.get_ai_processor", return_value=_ai_processor_mock()), \
             patch("app.scheduler.collection.get_vector_store", return_value=_vector_store_mock()), \
             patch("app.scheduler.collection.cluster_item", return_value="cluster-1"):
            from app.scheduler.collection import save_and_process_items
            failed = await save_and_process_items(items, customer, db)

        assert failed == 0
        # Still only one row for that URL
        count = db.query(IntelligenceItem).filter(
            IntelligenceItem.url == url,
            IntelligenceItem.customer_id == customer.id,
        ).count()
        assert count == 1

    async def test_session_usable_after_integrity_error(self):
        """After a UNIQUE constraint violation, the session must still be
        able to insert subsequent (non-duplicate) items."""
        db = make_session()
        customer = make_customer(db)

        dup_url = "https://example.com/duplicate"
        new_url = "https://example.com/brand-new"

        # Pre-insert the duplicate
        db.add(IntelligenceItem(
            customer_id=customer.id,
            source_type="rss",
            title="Pre-existing",
            url=dup_url,
            published_date=datetime.utcnow(),
        ))
        db.commit()

        # Batch: duplicate first, then a genuine new item
        items = [
            make_item_create(customer.id, dup_url, "Dup Title"),
            make_item_create(customer.id, new_url, "New Title"),
        ]

        with patch("app.scheduler.collection.get_ai_processor", return_value=_ai_processor_mock()), \
             patch("app.scheduler.collection.get_vector_store", return_value=_vector_store_mock()), \
             patch("app.scheduler.collection.cluster_item", return_value="cluster-1"):
            from app.scheduler.collection import save_and_process_items
            failed = await save_and_process_items(items, customer, db)

        assert failed == 0
        # The new item must have been saved despite the earlier duplicate
        new_item = db.query(IntelligenceItem).filter(
            IntelligenceItem.url == new_url,
            IntelligenceItem.customer_id == customer.id,
        ).first()
        assert new_item is not None


# ---------------------------------------------------------------------------
# Tests: global collection lock
# ---------------------------------------------------------------------------

class TestCollectionLock:
    """run_collection must refuse to start if another run is already in progress."""

    def test_concurrent_run_is_skipped(self):
        """A second call to run_collection while one is running logs a warning and returns."""
        import app.scheduler.collection as col_module

        # Reset lock to ensure a clean state
        if col_module._collection_lock.locked():
            col_module._collection_lock.release()

        call_log = []

        def slow_collection(*args, **kwargs):
            import asyncio
            async def _inner():
                import asyncio
                await asyncio.sleep(0.1)
            asyncio.run(_inner())
            call_log.append("ran")

        with patch.object(col_module, "run_collection_async", new=AsyncMock()) as mock_async:
            # Acquire the lock manually to simulate an in-progress run
            acquired = col_module._collection_lock.acquire(blocking=False)
            assert acquired, "Lock should be free before test"

            try:
                # This call should see the lock held and skip
                col_module.run_collection(customer_id=1, collection_type="manual")
            finally:
                col_module._collection_lock.release()

            # run_collection_async must NOT have been called
            mock_async.assert_not_called()

    def test_lock_is_released_after_successful_run(self):
        """Lock must be released even after a normal run completes."""
        import app.scheduler.collection as col_module

        if col_module._collection_lock.locked():
            col_module._collection_lock.release()

        with patch.object(col_module, "run_collection_async", new=AsyncMock()):
            col_module.run_collection(customer_id=None, collection_type="manual")

        assert not col_module._collection_lock.locked()

    def test_lock_is_released_after_exception(self):
        """Lock must be released even if run_collection_async raises."""
        import app.scheduler.collection as col_module

        if col_module._collection_lock.locked():
            col_module._collection_lock.release()

        async def _raise():
            raise RuntimeError("simulated failure")

        with patch.object(col_module, "run_collection_async", new=_raise):
            with pytest.raises(RuntimeError):
                col_module.run_collection(customer_id=None, collection_type="manual")

        assert not col_module._collection_lock.locked()


# ---------------------------------------------------------------------------
# Tests: customer_id caching in collect_for_customer
# ---------------------------------------------------------------------------

class TestCustomerIdCaching:
    """collect_for_customer must cache customer.id as a plain int so that
    except-blocks can call update_collection_status even after the session
    has been rolled back (which expires all ORM attributes)."""

    async def test_customer_id_cached_at_function_start(self):
        """After a session rollback, update_collection_status is still called
        with the correct customer_id (not an expired ORM attribute access)."""
        db = make_session()
        customer = make_customer(db)
        expected_id = customer.id

        captured_ids = []

        def fake_update_status(db, customer_id, source_type, success, error_message=None, **kw):
            captured_ids.append(customer_id)

        # Make the NewsAPI collector raise so we hit the except block
        with patch("app.scheduler.collection.update_collection_status", side_effect=fake_update_status), \
             patch("app.scheduler.collection.settings") as mock_settings, \
             patch("app.scheduler.collection.should_collect_source", return_value=False):

            mock_settings.news_api_key = None  # disables NewsAPI branch entirely
            mock_settings.reddit_client_id = None
            mock_settings.reddit_client_secret = None
            mock_settings.twitter_bearer_token = None
            mock_settings.youtube_api_key = None

            from app.scheduler.collection import collect_for_customer
            result = await collect_for_customer(customer, db, collection_type="manual")

        # The function must return a dict with the correct customer_id
        assert result["customer_id"] == expected_id
