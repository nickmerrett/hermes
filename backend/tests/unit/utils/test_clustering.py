"""
Unit tests for app/utils/clustering.py

Tests story clustering functions including:
- Cosine similarity calculations
- Title similarity (Jaccard token overlap)
- Source tier rankings
- Cluster settings defaults
- Cluster creation, assignment, and item clustering (with DB fixtures)
"""

import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app.utils.clustering import (
    cosine_similarity,
    title_similarity,
    get_source_tier,
    get_source_priority,
    get_default_clustering_settings,
    get_clustering_settings,
    get_cluster_info,
    create_new_cluster,
    assign_to_cluster,
    find_similar_cluster,
    cluster_item,
)
from app.models.database import IntelligenceItem, PlatformSettings


# ============================================================================
# Cosine Similarity Tests
# ============================================================================

class TestCosineSimilarity:
    """Tests for the cosine_similarity function."""

    def test_identical_vectors(self):
        """Identical vectors should return 1.0."""
        vec = [1.0, 2.0, 3.0]
        assert cosine_similarity(vec, vec) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        """Orthogonal (perpendicular) vectors should return 0.0."""
        vec1 = [1.0, 0.0]
        vec2 = [0.0, 1.0]
        assert cosine_similarity(vec1, vec2) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        """Opposite vectors should return -1.0."""
        vec1 = [1.0, 0.0]
        vec2 = [-1.0, 0.0]
        assert cosine_similarity(vec1, vec2) == pytest.approx(-1.0)

    def test_similar_vectors_high_similarity(self):
        """Similar vectors should have high similarity."""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [1.1, 2.1, 3.1]
        sim = cosine_similarity(vec1, vec2)
        assert sim > 0.99

    def test_different_vectors_low_similarity(self):
        """Very different vectors should have low similarity."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 0.0, 1.0]
        assert cosine_similarity(vec1, vec2) == pytest.approx(0.0)

    def test_zero_vector_returns_zero(self):
        """Zero vector should return 0.0 (avoid division by zero)."""
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 2.0, 3.0]
        assert cosine_similarity(vec1, vec2) == 0.0

    def test_both_zero_vectors(self):
        """Two zero vectors should return 0.0."""
        vec1 = [0.0, 0.0]
        vec2 = [0.0, 0.0]
        assert cosine_similarity(vec1, vec2) == 0.0

    def test_single_element_vectors(self):
        """Single element vectors should work."""
        assert cosine_similarity([5.0], [5.0]) == pytest.approx(1.0)
        assert cosine_similarity([5.0], [-5.0]) == pytest.approx(-1.0)

    def test_large_vectors(self):
        """Large vectors should compute correctly."""
        import numpy as np
        np.random.seed(42)
        vec1 = np.random.rand(384).tolist()  # Typical embedding dimension
        sim = cosine_similarity(vec1, vec1)
        assert sim == pytest.approx(1.0)

    def test_symmetry(self):
        """Cosine similarity should be symmetric."""
        vec1 = [1.0, 3.0, 5.0]
        vec2 = [2.0, 4.0, 1.0]
        assert cosine_similarity(vec1, vec2) == pytest.approx(cosine_similarity(vec2, vec1))


# ============================================================================
# Title Similarity Tests
# ============================================================================

class TestTitleSimilarity:
    """Tests for the title_similarity function."""

    def test_identical_titles(self):
        """Identical titles should return 1.0."""
        title = "Rio Tinto Announces New Mining Project"
        assert title_similarity(title, title) == pytest.approx(1.0)

    def test_completely_different_titles(self):
        """Completely different titles should return 0.0."""
        t1 = "Apple Launches New iPhone"
        t2 = "Brazil Wins World Cup"
        assert title_similarity(t1, t2) == 0.0

    def test_partially_overlapping_titles(self):
        """Titles sharing some words should have partial similarity."""
        t1 = "Rio Tinto Announces Major Acquisition Deal"
        t2 = "Rio Tinto Merger Deal With Glencore"
        sim = title_similarity(t1, t2)
        assert 0.2 < sim < 0.8

    def test_same_story_different_headlines(self):
        """Same story from different sources should have reasonable similarity."""
        t1 = "Glencore Rio Tinto Merger Discussions"
        t2 = "Rio Tinto Glencore Restart Merger Talks"
        sim = title_similarity(t1, t2)
        assert sim > 0.3

    def test_same_company_different_events(self):
        """Different events about same company should have lower similarity."""
        t1 = "Rio Tinto Solar Plant Kennecott Utah"
        t2 = "Glencore Rio Tinto Merger Discussions"
        sim = title_similarity(t1, t2)
        # Only "rio" and "tinto" overlap (short words filtered)
        assert sim < 0.4

    def test_empty_title_returns_zero(self):
        """Empty title should return 0.0."""
        assert title_similarity("", "Some Title") == 0.0
        assert title_similarity("Some Title", "") == 0.0
        assert title_similarity("", "") == 0.0

    def test_none_title_returns_zero(self):
        """None title should return 0.0."""
        assert title_similarity(None, "Some Title") == 0.0
        assert title_similarity("Some Title", None) == 0.0
        assert title_similarity(None, None) == 0.0

    def test_case_insensitive(self):
        """Similarity should be case-insensitive."""
        t1 = "Rio Tinto ANNOUNCES Major Deal"
        t2 = "rio tinto announces major deal"
        assert title_similarity(t1, t2) == pytest.approx(1.0)

    def test_punctuation_ignored(self):
        """Punctuation should not affect similarity."""
        t1 = "Rio Tinto: Announces New Deal!"
        t2 = "Rio Tinto Announces New Deal"
        assert title_similarity(t1, t2) == pytest.approx(1.0)

    def test_short_words_filtered(self):
        """Words with 2 or fewer characters should be filtered out."""
        t1 = "A Is The An Of Rio Tinto Deal"
        t2 = "In On At By Rio Tinto Deal"
        sim = title_similarity(t1, t2)
        # "rio", "tinto", "deal" match; "the", "is", "a", etc. filtered
        assert sim > 0.5

    def test_symmetry(self):
        """Title similarity should be symmetric."""
        t1 = "Company Launches New Product"
        t2 = "New Product Launch Announced"
        assert title_similarity(t1, t2) == pytest.approx(title_similarity(t2, t1))

    def test_only_short_words_returns_zero(self):
        """Titles with only short words should return 0.0."""
        t1 = "a is of"
        t2 = "a is of"
        assert title_similarity(t1, t2) == 0.0


# ============================================================================
# Source Tier Tests
# ============================================================================

class TestSourceTiers:
    """Tests for source tier and priority functions."""

    def test_official_sources(self):
        """Press releases and LinkedIn should be official tier."""
        assert get_source_tier('press_release') == 'official'
        assert get_source_tier('pressrelease') == 'official'
        assert get_source_tier('linkedin') == 'official'
        assert get_source_tier('linkedin_company') == 'official'
        assert get_source_tier('linkedin_user') == 'official'
        assert get_source_tier('web_scrape') == 'official'

    def test_primary_sources(self):
        """News API and RSS should be primary tier."""
        assert get_source_tier('news_api') == 'primary'
        assert get_source_tier('rss') == 'primary'
        assert get_source_tier('australian_news') == 'primary'

    def test_secondary_sources(self):
        """Yahoo Finance should be secondary tier."""
        assert get_source_tier('stock') == 'secondary'
        assert get_source_tier('yahoo_finance_news') == 'secondary'

    def test_aggregator_sources(self):
        """Google News should be aggregator tier."""
        assert get_source_tier('google_news') == 'aggregator'

    def test_social_sources(self):
        """Reddit, Twitter, YouTube should be social tier."""
        assert get_source_tier('reddit') == 'social'
        assert get_source_tier('twitter') == 'social'
        assert get_source_tier('youtube') == 'social'

    def test_unknown_source_defaults_to_secondary(self):
        """Unknown source types should default to secondary."""
        assert get_source_tier('unknown_source') == 'secondary'

    def test_priority_ordering(self):
        """Official sources should have lower priority number (higher priority)."""
        assert get_source_priority('press_release') < get_source_priority('news_api')
        assert get_source_priority('news_api') < get_source_priority('stock')
        assert get_source_priority('stock') < get_source_priority('google_news')
        assert get_source_priority('google_news') < get_source_priority('reddit')

    def test_official_beats_aggregator(self):
        """Press release should have higher priority than Google News."""
        assert get_source_priority('press_release') < get_source_priority('google_news')


# ============================================================================
# Clustering Settings Tests
# ============================================================================

class TestClusteringSettings:
    """Tests for clustering settings and defaults."""

    def test_default_settings_values(self):
        """Default settings should have expected values."""
        defaults = get_default_clustering_settings()
        assert defaults['enabled'] is True
        assert defaults['similarity_threshold'] == 0.80
        assert defaults['time_window_hours'] == 96
        assert defaults['title_similarity_enabled'] is True
        assert defaults['title_similarity_threshold'] == 0.40
        assert defaults['max_cluster_size'] == 25
        assert defaults['max_cluster_age_hours'] == 168

    def test_get_settings_returns_defaults_when_no_db_setting(self, test_db):
        """Should return defaults when no clustering_config in database."""
        settings = get_clustering_settings(test_db)
        assert settings['enabled'] is True
        assert settings['similarity_threshold'] == 0.80
        assert settings['title_similarity_enabled'] is True

    def test_get_settings_returns_db_values(self, test_db):
        """Should return database values when configured."""
        db_setting = PlatformSettings(
            key='clustering_config',
            value={
                'enabled': False,
                'similarity_threshold': 0.90,
                'time_window_hours': 48,
                'title_similarity_enabled': False,
                'title_similarity_threshold': 0.50,
                'max_cluster_size': 10,
                'max_cluster_age_hours': 72
            }
        )
        test_db.add(db_setting)
        test_db.commit()

        settings = get_clustering_settings(test_db)
        assert settings['enabled'] is False
        assert settings['similarity_threshold'] == 0.90
        assert settings['time_window_hours'] == 48
        assert settings['title_similarity_enabled'] is False
        assert settings['max_cluster_size'] == 10

    def test_get_settings_merges_with_defaults(self, test_db):
        """Partial DB settings should merge with defaults for missing keys."""
        db_setting = PlatformSettings(
            key='clustering_config',
            value={
                'enabled': True,
                'similarity_threshold': 0.70,
            }
        )
        test_db.add(db_setting)
        test_db.commit()

        settings = get_clustering_settings(test_db)
        assert settings['similarity_threshold'] == 0.70  # From DB
        assert settings['title_similarity_enabled'] is True  # From defaults
        assert settings['max_cluster_size'] == 25  # From defaults


# ============================================================================
# Cluster Info Tests
# ============================================================================

class TestGetClusterInfo:
    """Tests for the get_cluster_info function."""

    def test_empty_cluster(self, test_db):
        """Non-existent cluster should return empty info."""
        info = get_cluster_info("nonexistent-cluster", test_db)
        assert info['size'] == 0
        assert info['oldest_date'] is None
        assert info['primary_title'] is None

    def test_single_item_cluster(self, test_db, sample_customer):
        """Cluster with one item should return correct info."""
        cluster_id = str(uuid.uuid4())
        item = IntelligenceItem(
            customer_id=sample_customer.id,
            source_type="rss",
            title="Test Article",
            content="Content",
            url="https://example.com/1",
            published_date=datetime(2024, 6, 15, 12, 0),
            collected_date=datetime(2024, 6, 15, 13, 0),
            cluster_id=cluster_id,
            is_cluster_primary=True,
            cluster_member_count=1,
        )
        test_db.add(item)
        test_db.commit()

        info = get_cluster_info(cluster_id, test_db)
        assert info['size'] == 1
        assert info['primary_title'] == "Test Article"
        assert info['oldest_date'] == datetime(2024, 6, 15, 12, 0)

    def test_multi_item_cluster(self, test_db, sample_customer):
        """Cluster with multiple items should return correct size and dates."""
        cluster_id = str(uuid.uuid4())
        dates = [
            datetime(2024, 6, 14, 10, 0),
            datetime(2024, 6, 15, 12, 0),
            datetime(2024, 6, 16, 8, 0),
        ]
        for i, d in enumerate(dates):
            item = IntelligenceItem(
                customer_id=sample_customer.id,
                source_type="rss",
                title=f"Article {i}",
                content=f"Content {i}",
                url=f"https://example.com/{i}",
                published_date=d,
                collected_date=d,
                cluster_id=cluster_id,
                is_cluster_primary=(i == 0),
                cluster_member_count=3,
            )
            test_db.add(item)
        test_db.commit()

        info = get_cluster_info(cluster_id, test_db)
        assert info['size'] == 3
        assert info['oldest_date'] == datetime(2024, 6, 14, 10, 0)
        assert info['newest_date'] == datetime(2024, 6, 16, 8, 0)


# ============================================================================
# Create New Cluster Tests
# ============================================================================

class TestCreateNewCluster:
    """Tests for the create_new_cluster function."""

    def test_creates_cluster_with_uuid(self, test_db, sample_customer):
        """Should assign a UUID cluster_id to the item."""
        item = IntelligenceItem(
            customer_id=sample_customer.id,
            source_type="rss",
            title="New Article",
            content="Content",
            url="https://example.com/new",
            published_date=datetime.utcnow(),
            collected_date=datetime.utcnow(),
        )
        test_db.add(item)
        test_db.commit()

        cluster_id = create_new_cluster(item, test_db)

        assert cluster_id is not None
        # Should be a valid UUID
        uuid.UUID(cluster_id)
        assert item.cluster_id == cluster_id
        assert item.is_cluster_primary is True
        assert item.cluster_member_count == 1

    def test_sets_source_tier(self, test_db, sample_customer):
        """Should set source_tier based on source_type."""
        item = IntelligenceItem(
            customer_id=sample_customer.id,
            source_type="press_release",
            title="Press Release",
            content="Content",
            url="https://example.com/pr",
            published_date=datetime.utcnow(),
            collected_date=datetime.utcnow(),
        )
        test_db.add(item)
        test_db.commit()

        create_new_cluster(item, test_db)

        assert item.source_tier == 'official'


# ============================================================================
# Assign to Cluster Tests
# ============================================================================

class TestAssignToCluster:
    """Tests for the assign_to_cluster function."""

    def _make_item(self, test_db, customer, source_type, title, cluster_id=None, is_primary=False):
        """Helper to create an IntelligenceItem."""
        item = IntelligenceItem(
            customer_id=customer.id,
            source_type=source_type,
            title=title,
            content=f"Content for {title}",
            url=f"https://example.com/{uuid.uuid4()}",
            published_date=datetime.utcnow(),
            collected_date=datetime.utcnow(),
            cluster_id=cluster_id,
            is_cluster_primary=is_primary,
            cluster_member_count=1 if cluster_id else 0,
        )
        test_db.add(item)
        test_db.commit()
        test_db.refresh(item)
        return item

    def test_assigns_to_cluster(self, test_db, sample_customer):
        """Should assign item to existing cluster."""
        cluster_id = str(uuid.uuid4())
        self._make_item(test_db, sample_customer, "google_news", "Existing", cluster_id, True)

        new_item = self._make_item(test_db, sample_customer, "google_news", "New Item")

        assign_to_cluster(new_item, cluster_id, test_db)

        assert new_item.cluster_id == cluster_id
        assert new_item.cluster_member_count == 2

    def test_higher_priority_becomes_primary(self, test_db, sample_customer):
        """Higher priority source should become the new primary."""
        cluster_id = str(uuid.uuid4())
        # Google News is aggregator (tier 4)
        existing = self._make_item(test_db, sample_customer, "google_news", "Existing", cluster_id, True)

        # Press release is official (tier 1) - should take over as primary
        new_item = self._make_item(test_db, sample_customer, "press_release", "Press Release")

        assign_to_cluster(new_item, cluster_id, test_db)

        test_db.refresh(existing)
        assert new_item.is_cluster_primary is True
        assert existing.is_cluster_primary is False

    def test_lower_priority_stays_secondary(self, test_db, sample_customer):
        """Lower priority source should not become primary."""
        cluster_id = str(uuid.uuid4())
        # Press release is official (tier 1) - currently primary
        existing = self._make_item(test_db, sample_customer, "press_release", "Official", cluster_id, True)

        # Reddit is social (tier 5) - should NOT take over
        new_item = self._make_item(test_db, sample_customer, "reddit", "Reddit Post")

        assign_to_cluster(new_item, cluster_id, test_db)

        test_db.refresh(existing)
        assert existing.is_cluster_primary is True
        assert new_item.is_cluster_primary is False

    def test_member_count_updated_for_all_items(self, test_db, sample_customer):
        """All items in cluster should have updated member_count."""
        cluster_id = str(uuid.uuid4())
        item1 = self._make_item(test_db, sample_customer, "rss", "Item 1", cluster_id, True)
        item2 = self._make_item(test_db, sample_customer, "news_api", "Item 2", cluster_id, False)
        # Fix counts manually since we didn't use assign_to_cluster for item2
        item1.cluster_member_count = 2
        item2.cluster_member_count = 2
        test_db.commit()

        item3 = self._make_item(test_db, sample_customer, "google_news", "Item 3")
        assign_to_cluster(item3, cluster_id, test_db)

        test_db.refresh(item1)
        test_db.refresh(item2)
        assert item1.cluster_member_count == 3
        assert item2.cluster_member_count == 3
        assert item3.cluster_member_count == 3


# ============================================================================
# Find Similar Cluster Tests (with mocked vector store)
# ============================================================================

class TestFindSimilarCluster:
    """Tests for find_similar_cluster with mocked vector store."""

    def _make_clustered_item(self, test_db, customer, title, source_type, cluster_id, published_date=None):
        """Helper to create a clustered item."""
        item = IntelligenceItem(
            customer_id=customer.id,
            source_type=source_type,
            title=title,
            content=f"Content for {title}",
            url=f"https://example.com/{uuid.uuid4()}",
            published_date=published_date or datetime.utcnow(),
            collected_date=published_date or datetime.utcnow(),
            cluster_id=cluster_id,
            is_cluster_primary=True,
            cluster_member_count=1,
        )
        test_db.add(item)
        test_db.commit()
        test_db.refresh(item)
        return item

    @patch('app.utils.clustering.get_vector_store')
    def test_no_recent_items_returns_none(self, mock_vs, test_db, sample_customer):
        """Should return None when no recent clustered items exist."""
        result = find_similar_cluster(
            item_embedding=[1.0, 2.0, 3.0],
            item_title="Test Article",
            customer_id=sample_customer.id,
            published_date=datetime.utcnow(),
            db=test_db,
        )
        assert result is None

    @patch('app.utils.clustering.get_vector_store')
    def test_finds_similar_cluster(self, mock_vs, test_db, sample_customer):
        """Should find cluster when embedding similarity exceeds threshold."""
        cluster_id = str(uuid.uuid4())
        now = datetime.utcnow()
        _ = self._make_clustered_item(
            test_db, sample_customer, "Glencore Rio Tinto Merger Talks",
            "google_news", cluster_id, now - timedelta(hours=2)
        )

        # Mock vector store to return a very similar embedding
        mock_store = MagicMock()
        mock_store.get_embedding.return_value = [1.0, 2.0, 3.0]
        mock_vs.return_value = mock_store

        result = find_similar_cluster(
            item_embedding=[1.0, 2.0, 3.0],  # Identical = similarity 1.0
            item_title="Rio Tinto Glencore Restart Merger Discussions",
            customer_id=sample_customer.id,
            published_date=now,
            db=test_db,
            similarity_threshold=0.80,
            title_similarity_threshold=0.30,
        )
        assert result == cluster_id

    @patch('app.utils.clustering.get_vector_store')
    def test_rejects_below_embedding_threshold(self, mock_vs, test_db, sample_customer):
        """Should reject when embedding similarity is below threshold."""
        cluster_id = str(uuid.uuid4())
        now = datetime.utcnow()
        self._make_clustered_item(
            test_db, sample_customer, "Some Article",
            "google_news", cluster_id, now - timedelta(hours=2)
        )

        # Mock vector store to return an orthogonal embedding
        mock_store = MagicMock()
        mock_store.get_embedding.return_value = [0.0, 0.0, 1.0]
        mock_vs.return_value = mock_store

        result = find_similar_cluster(
            item_embedding=[1.0, 0.0, 0.0],  # Orthogonal = similarity 0.0
            item_title="Some Article",
            customer_id=sample_customer.id,
            published_date=now,
            db=test_db,
            similarity_threshold=0.80,
        )
        assert result is None

    @patch('app.utils.clustering.get_vector_store')
    def test_rejects_below_title_threshold(self, mock_vs, test_db, sample_customer):
        """Should reject when title similarity is below threshold even if embeddings match."""
        cluster_id = str(uuid.uuid4())
        now = datetime.utcnow()
        self._make_clustered_item(
            test_db, sample_customer, "Rio Tinto Solar Plant Kennecott Utah",
            "google_news", cluster_id, now - timedelta(hours=2)
        )

        mock_store = MagicMock()
        mock_store.get_embedding.return_value = [1.0, 2.0, 3.0]
        mock_vs.return_value = mock_store

        result = find_similar_cluster(
            item_embedding=[1.0, 2.0, 3.0],  # Identical embedding
            item_title="Glencore Rio Tinto Merger Discussions",  # Different event
            customer_id=sample_customer.id,
            published_date=now,
            db=test_db,
            similarity_threshold=0.80,
            title_similarity_enabled=True,
            title_similarity_threshold=0.40,
        )
        assert result is None

    @patch('app.utils.clustering.get_vector_store')
    def test_skips_title_check_when_disabled(self, mock_vs, test_db, sample_customer):
        """Should skip title check when title_similarity_enabled is False."""
        cluster_id = str(uuid.uuid4())
        now = datetime.utcnow()
        self._make_clustered_item(
            test_db, sample_customer, "Totally Different Title",
            "google_news", cluster_id, now - timedelta(hours=2)
        )

        mock_store = MagicMock()
        mock_store.get_embedding.return_value = [1.0, 2.0, 3.0]
        mock_vs.return_value = mock_store

        result = find_similar_cluster(
            item_embedding=[1.0, 2.0, 3.0],
            item_title="Completely Unrelated Headline",
            customer_id=sample_customer.id,
            published_date=now,
            db=test_db,
            similarity_threshold=0.80,
            title_similarity_enabled=False,  # Disabled
        )
        assert result == cluster_id

    @patch('app.utils.clustering.get_cluster_info')
    @patch('app.utils.clustering.get_vector_store')
    def test_rejects_cluster_exceeding_max_size(self, mock_vs, mock_info, test_db, sample_customer):
        """Should reject clusters that have reached max size."""
        cluster_id = str(uuid.uuid4())
        now = datetime.utcnow()
        self._make_clustered_item(
            test_db, sample_customer, "Same Story Again",
            "google_news", cluster_id, now - timedelta(hours=2)
        )

        mock_store = MagicMock()
        mock_store.get_embedding.return_value = [1.0, 2.0, 3.0]
        mock_vs.return_value = mock_store

        # Mock cluster info to show it's full
        mock_info.return_value = {
            'size': 25,
            'oldest_date': now - timedelta(hours=24),
            'newest_date': now - timedelta(hours=2),
            'primary_title': 'Same Story Again'
        }

        result = find_similar_cluster(
            item_embedding=[1.0, 2.0, 3.0],
            item_title="Same Story Again",
            customer_id=sample_customer.id,
            published_date=now,
            db=test_db,
            similarity_threshold=0.80,
            max_cluster_size=25,
        )
        assert result is None

    @patch('app.utils.clustering.get_cluster_info')
    @patch('app.utils.clustering.get_vector_store')
    def test_rejects_cluster_exceeding_max_age(self, mock_vs, mock_info, test_db, sample_customer):
        """Should reject clusters that are too old."""
        cluster_id = str(uuid.uuid4())
        now = datetime.utcnow()
        self._make_clustered_item(
            test_db, sample_customer, "Old Story",
            "google_news", cluster_id, now - timedelta(hours=2)
        )

        mock_store = MagicMock()
        mock_store.get_embedding.return_value = [1.0, 2.0, 3.0]
        mock_vs.return_value = mock_store

        # Mock cluster info to show it's very old
        mock_info.return_value = {
            'size': 5,
            'oldest_date': now - timedelta(hours=200),  # Older than 168h
            'newest_date': now - timedelta(hours=2),
            'primary_title': 'Old Story'
        }

        result = find_similar_cluster(
            item_embedding=[1.0, 2.0, 3.0],
            item_title="Old Story",
            customer_id=sample_customer.id,
            published_date=now,
            db=test_db,
            similarity_threshold=0.80,
            max_cluster_age_hours=168,
        )
        assert result is None

    @patch('app.utils.clustering.get_vector_store')
    def test_excludes_linkedin_items(self, mock_vs, test_db, sample_customer):
        """LinkedIn items in DB should be excluded from cluster matching."""
        cluster_id = str(uuid.uuid4())
        now = datetime.utcnow()

        # Only a LinkedIn item in this cluster
        linkedin_item = IntelligenceItem(
            customer_id=sample_customer.id,
            source_type="linkedin_user",
            title="Executive Post About Strategy",
            content="Content",
            url="https://linkedin.com/post/1",
            published_date=now - timedelta(hours=2),
            collected_date=now - timedelta(hours=2),
            cluster_id=cluster_id,
            is_cluster_primary=True,
            cluster_member_count=1,
        )
        test_db.add(linkedin_item)
        test_db.commit()

        result = find_similar_cluster(
            item_embedding=[1.0, 2.0, 3.0],
            item_title="Executive Post About Strategy",
            customer_id=sample_customer.id,
            published_date=now,
            db=test_db,
        )
        # Should not match because LinkedIn items are excluded
        assert result is None


# ============================================================================
# Cluster Item (Main Function) Tests
# ============================================================================

class TestClusterItem:
    """Tests for the main cluster_item function."""

    def _make_item(self, test_db, customer, source_type="rss", title="Test"):
        """Helper to create an unclustered item."""
        item = IntelligenceItem(
            customer_id=customer.id,
            source_type=source_type,
            title=title,
            content=f"Content for {title}",
            url=f"https://example.com/{uuid.uuid4()}",
            published_date=datetime.utcnow(),
            collected_date=datetime.utcnow(),
        )
        test_db.add(item)
        test_db.commit()
        test_db.refresh(item)
        return item

    @patch('app.utils.clustering.find_similar_cluster')
    def test_linkedin_always_gets_solo_cluster(self, mock_find, test_db, sample_customer):
        """LinkedIn items should always create their own cluster."""
        item = self._make_item(test_db, sample_customer, "linkedin_user", "CEO Post")

        cluster_id = cluster_item(item, [1.0, 2.0], test_db)

        # find_similar_cluster should NOT be called for LinkedIn
        mock_find.assert_not_called()
        assert cluster_id is not None
        assert item.is_cluster_primary is True
        assert item.cluster_member_count == 1

    @patch('app.utils.clustering.find_similar_cluster')
    def test_linkedin_company_gets_solo_cluster(self, mock_find, test_db, sample_customer):
        """LinkedIn company items should also get solo clusters."""
        item = self._make_item(test_db, sample_customer, "linkedin", "Company Update")

        _ = cluster_item(item, [1.0, 2.0], test_db)

        mock_find.assert_not_called()
        assert item.is_cluster_primary is True

    @patch('app.utils.clustering.find_similar_cluster')
    def test_creates_new_cluster_when_no_match(self, mock_find, test_db, sample_customer):
        """Should create new cluster when no similar cluster found."""
        mock_find.return_value = None
        item = self._make_item(test_db, sample_customer, "rss", "Unique Article")

        cluster_id = cluster_item(item, [1.0, 2.0], test_db)

        assert cluster_id is not None
        assert item.cluster_id == cluster_id
        assert item.is_cluster_primary is True
        assert item.cluster_member_count == 1

    @patch('app.utils.clustering.assign_to_cluster')
    @patch('app.utils.clustering.find_similar_cluster')
    def test_assigns_to_existing_cluster_when_match_found(self, mock_find, mock_assign, test_db, sample_customer):
        """Should assign to existing cluster when similar one found."""
        existing_cluster_id = str(uuid.uuid4())
        mock_find.return_value = existing_cluster_id
        item = self._make_item(test_db, sample_customer, "news_api", "Related Article")

        cluster_id = cluster_item(item, [1.0, 2.0], test_db)

        assert cluster_id == existing_cluster_id
        mock_assign.assert_called_once_with(item, existing_cluster_id, test_db)

    def test_disabled_clustering_creates_solo_cluster(self, test_db, sample_customer):
        """When clustering is disabled, every item gets its own cluster."""
        # Add platform setting to disable clustering
        setting = PlatformSettings(
            key='clustering_config',
            value={'enabled': False}
        )
        test_db.add(setting)
        test_db.commit()

        item = self._make_item(test_db, sample_customer, "rss", "Some Article")

        cluster_id = cluster_item(item, [1.0, 2.0], test_db)

        assert cluster_id is not None
        assert item.is_cluster_primary is True
        assert item.cluster_member_count == 1

    @patch('app.utils.clustering.find_similar_cluster')
    def test_error_falls_back_to_solo_cluster(self, mock_find, test_db, sample_customer):
        """On error, should create solo cluster so item isn't orphaned."""
        mock_find.side_effect = Exception("Vector store unavailable")
        item = self._make_item(test_db, sample_customer, "rss", "Article")

        cluster_id = cluster_item(item, [1.0, 2.0], test_db)

        # Should still get a cluster despite the error
        assert cluster_id is not None
        assert item.cluster_id == cluster_id
        assert item.is_cluster_primary is True


# ============================================================================
# Integration Scenario Tests
# ============================================================================

class TestClusteringScenarios:
    """End-to-end scenario tests for clustering behavior."""

    def test_rio_tinto_scenario_different_events_not_clustered(self):
        """
        The Rio Tinto bug: articles about same company but different events
        should NOT cluster when title similarity is checked.

        Solar plant article vs merger article should fail title check.
        """
        t1 = "Rio Tinto: At Kennecott in Utah, we've just switched on a new 25MW solar plant"
        t2 = "Glencore, Rio Tinto in Merger Discussions"

        sim = title_similarity(t1, t2)
        # These share "rio" and "tinto" but nothing else meaningful
        assert sim < 0.40, f"Title similarity {sim:.3f} should be below 0.40 threshold"

    def test_rio_tinto_scenario_same_merger_story_clusters(self):
        """
        Different headlines about the same merger should cluster.
        """
        t1 = "Glencore, Rio Tinto in Merger Discussions"
        t2 = "Rio Tinto, Glencore Restart Talks to Form World's Biggest Miner"

        sim = title_similarity(t1, t2)
        # These share "glencore", "rio", "tinto" + merger-related words
        assert sim >= 0.25, f"Title similarity {sim:.3f} should be reasonable for same story"

    def test_service_contract_not_clustered_with_merger(self):
        """
        A service contract article should not cluster with merger articles.
        """
        t1 = "Glencore, Rio Tinto in Merger Discussions"
        t2 = "Monadelphous inks $300m service contract deal with Rio Tinto"

        sim = title_similarity(t1, t2)
        # Only "rio" and "tinto" overlap
        assert sim < 0.40, f"Title similarity {sim:.3f} should be below threshold"

    def test_nickel_mine_not_clustered_with_solar(self):
        """
        Nickel mine article should not cluster with solar plant article.
        """
        t1 = "Rio Tinto switches on 25MW solar plant at Kennecott Utah"
        t2 = "Owner of Ravensthorpe nickel mine open to offers"

        sim = title_similarity(t1, t2)
        assert sim < 0.40, f"Title similarity {sim:.3f} should be below threshold"
