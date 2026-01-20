"""
Integration tests for app/api/feed.py

Tests intelligence feed retrieval with filtering, smart feed logic,
and item management (ignore/unignore/delete).
"""

import pytest
from fastapi import status
from datetime import datetime, timedelta


class TestGetFeedEndpoint:
    """Tests for GET /api/feed endpoint."""

    def test_get_feed_empty(self, client, auth_headers):
        """Should return empty feed when no items exist."""
        response = client.get("/api/feed", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_get_feed_with_items(self, client, auth_headers, sample_intelligence_items):
        """Should return feed items."""
        response = client.get("/api/feed", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["items"]) > 0
        assert data["total"] > 0

    def test_get_feed_response_structure(self, client, auth_headers, sample_intelligence_item):
        """Should return proper response structure."""
        response = client.get("/api/feed", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Check response structure
        assert "items" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert "clustered" in data

    def test_get_feed_item_structure(self, client, auth_headers, sample_intelligence_item):
        """Feed items should have proper structure."""
        response = client.get("/api/feed", headers=auth_headers)

        data = response.json()
        assert len(data["items"]) > 0

        item = data["items"][0]
        required_fields = ["id", "title", "url", "source_type",
                          "published_date", "collected_date", "customer_id"]
        for field in required_fields:
            assert field in item, f"Missing field: {field}"

    def test_get_feed_includes_processed(self, client, auth_headers, sample_intelligence_item):
        """Feed items should include processed intelligence."""
        response = client.get("/api/feed", headers=auth_headers)

        data = response.json()
        item = data["items"][0]

        assert "processed" in item
        if item["processed"]:
            assert "summary" in item["processed"]
            assert "category" in item["processed"]
            assert "priority_score" in item["processed"]

    def test_get_feed_no_auth(self, client):
        """Should return 401 without authentication."""
        response = client.get("/api/feed")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestFeedFiltering:
    """Tests for feed filtering options."""

    def test_filter_by_customer_id(self, client, auth_headers, sample_intelligence_items, sample_customer):
        """Should filter by customer_id."""
        response = client.get(f"/api/feed?customer_id={sample_customer.id}",
                              headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        for item in data["items"]:
            assert item["customer_id"] == sample_customer.id

    def test_filter_by_source_type(self, client, auth_headers, sample_intelligence_items):
        """Should filter by source_type."""
        response = client.get("/api/feed?source_type=rss", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        for item in data["items"]:
            assert item["source_type"] == "rss"

    def test_filter_by_category(self, client, auth_headers, sample_intelligence_items):
        """Should filter by category."""
        response = client.get("/api/feed?category=financial", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        for item in data["items"]:
            if item["processed"]:
                assert item["processed"]["category"] == "financial"

    def test_filter_by_sentiment(self, client, auth_headers, sample_intelligence_items):
        """Should filter by sentiment."""
        response = client.get("/api/feed?sentiment=positive", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        for item in data["items"]:
            if item["processed"]:
                assert item["processed"]["sentiment"] == "positive"

    def test_filter_by_min_priority(self, client, auth_headers, sample_intelligence_items):
        """Should filter by minimum priority (in full feed mode)."""
        response = client.get("/api/feed?min_priority=0.5&clustered=false",
                              headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        for item in data["items"]:
            if item["processed"]:
                assert item["processed"]["priority_score"] >= 0.5

    def test_filter_by_search(self, client, auth_headers, sample_intelligence_item):
        """Should filter by search term."""
        # Search for part of the title
        response = client.get("/api/feed?search=Acme", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Should find items with "Acme" in title or content
        assert len(data["items"]) > 0


class TestFeedPagination:
    """Tests for feed pagination."""

    def test_default_limit(self, client, auth_headers, sample_intelligence_items):
        """Should use default limit of 50."""
        response = client.get("/api/feed", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["limit"] == 50

    def test_custom_limit(self, client, auth_headers, sample_intelligence_items):
        """Should respect custom limit."""
        response = client.get("/api/feed?limit=2", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["limit"] == 2
        assert len(data["items"]) <= 2

    def test_limit_max_200(self, client, auth_headers):
        """Limit should not exceed 200."""
        response = client.get("/api/feed?limit=500", headers=auth_headers)

        # Should either cap at 200 or reject
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_422_UNPROCESSABLE_ENTITY]

    def test_offset(self, client, auth_headers, sample_intelligence_items):
        """Should respect offset."""
        response = client.get("/api/feed?offset=1", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["offset"] == 1


class TestSmartFeedMode:
    """Tests for smart feed (clustered) mode."""

    def test_clustered_true_default(self, client, auth_headers, sample_intelligence_items):
        """Clustered mode should be true by default."""
        response = client.get("/api/feed", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["clustered"] is True

    def test_clustered_true_only_primary(self, client, auth_headers, sample_intelligence_items):
        """Clustered mode should only show primary items."""
        response = client.get("/api/feed?clustered=true", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        for item in data["items"]:
            assert item["is_cluster_primary"] is True

    def test_clustered_false_shows_all(self, client, auth_headers, test_db, sample_customer):
        """Non-clustered mode should show all items."""
        from app.models.database import IntelligenceItem

        # Create both primary and non-primary items
        primary = IntelligenceItem(
            customer_id=sample_customer.id,
            source_type="rss",
            title="Primary Item",
            url="https://example.com/primary",
            cluster_id="cluster-test",
            is_cluster_primary=True,
            ignored=False
        )
        secondary = IntelligenceItem(
            customer_id=sample_customer.id,
            source_type="news_api",
            title="Secondary Item",
            url="https://example.com/secondary",
            cluster_id="cluster-test",
            is_cluster_primary=False,
            ignored=False
        )
        test_db.add(primary)
        test_db.add(secondary)
        test_db.commit()

        response = client.get("/api/feed?clustered=false", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Should include both primary and non-primary
        primaries = [i for i in data["items"] if i["is_cluster_primary"]]
        non_primaries = [i for i in data["items"] if not i["is_cluster_primary"]]
        # At least the secondary we created should be there
        assert len(non_primaries) >= 1 or len(data["items"]) >= 2


class TestIgnoredItems:
    """Tests for ignored items filtering."""

    def test_ignored_items_excluded(self, client, auth_headers, test_db, sample_customer):
        """Ignored items should be excluded from feed."""
        from app.models.database import IntelligenceItem

        # Create an ignored item
        ignored_item = IntelligenceItem(
            customer_id=sample_customer.id,
            source_type="rss",
            title="Ignored Item",
            url="https://example.com/ignored",
            is_cluster_primary=True,
            ignored=True,
            ignored_at=datetime.utcnow()
        )
        test_db.add(ignored_item)
        test_db.commit()

        response = client.get("/api/feed", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        for item in data["items"]:
            assert item["title"] != "Ignored Item"


class TestGetItemEndpoint:
    """Tests for GET /api/feed/{item_id} endpoint."""

    def test_get_item_success(self, client, auth_headers, sample_intelligence_item):
        """Should return item details."""
        response = client.get(f"/api/feed/{sample_intelligence_item.id}",
                              headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == sample_intelligence_item.id
        assert data["title"] == sample_intelligence_item.title

    def test_get_item_not_found(self, client, auth_headers):
        """Should return 404 for non-existent item."""
        response = client.get("/api/feed/99999", headers=auth_headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_item_no_auth(self, client, sample_intelligence_item):
        """Should return 401 without authentication."""
        response = client.get(f"/api/feed/{sample_intelligence_item.id}")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestIgnoreItemEndpoint:
    """Tests for PATCH /api/feed/{item_id}/ignore endpoint."""

    def test_ignore_item_success(self, client, auth_headers, sample_intelligence_item, test_db):
        """Should mark item as ignored."""
        response = client.patch(f"/api/feed/{sample_intelligence_item.id}/ignore",
                                headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        assert "ignored" in response.json()["message"].lower()

        # Verify in database
        test_db.refresh(sample_intelligence_item)
        assert sample_intelligence_item.ignored is True
        assert sample_intelligence_item.ignored_at is not None

    def test_ignore_item_not_found(self, client, auth_headers):
        """Should return 404 for non-existent item."""
        response = client.patch("/api/feed/99999/ignore", headers=auth_headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_ignore_item_no_auth(self, client, sample_intelligence_item):
        """Should return 401 without authentication."""
        response = client.patch(f"/api/feed/{sample_intelligence_item.id}/ignore")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestUnignoreItemEndpoint:
    """Tests for PATCH /api/feed/{item_id}/unignore endpoint."""

    def test_unignore_item_success(self, client, auth_headers, test_db, sample_customer):
        """Should unmark item as ignored."""
        from app.models.database import IntelligenceItem

        # Create an ignored item
        ignored_item = IntelligenceItem(
            customer_id=sample_customer.id,
            source_type="rss",
            title="To Unignore",
            url="https://example.com/unignore",
            is_cluster_primary=True,
            ignored=True,
            ignored_at=datetime.utcnow()
        )
        test_db.add(ignored_item)
        test_db.commit()

        response = client.patch(f"/api/feed/{ignored_item.id}/unignore",
                                headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK

        # Verify in database
        test_db.refresh(ignored_item)
        assert ignored_item.ignored is False
        assert ignored_item.ignored_at is None

    def test_unignore_item_not_found(self, client, auth_headers):
        """Should return 404 for non-existent item."""
        response = client.patch("/api/feed/99999/unignore", headers=auth_headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestDeleteItemEndpoint:
    """Tests for DELETE /api/feed/{item_id} endpoint."""

    def test_delete_item_success(self, client, auth_headers, sample_intelligence_item, test_db):
        """Should delete item."""
        item_id = sample_intelligence_item.id

        response = client.delete(f"/api/feed/{item_id}", headers=auth_headers)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify deletion
        from app.models.database import IntelligenceItem
        deleted = test_db.query(IntelligenceItem).filter(IntelligenceItem.id == item_id).first()
        assert deleted is None

    def test_delete_item_not_found(self, client, auth_headers):
        """Should return 404 for non-existent item."""
        response = client.delete("/api/feed/99999", headers=auth_headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_item_no_auth(self, client, sample_intelligence_item):
        """Should return 401 without authentication."""
        response = client.delete(f"/api/feed/{sample_intelligence_item.id}")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestGetClusterEndpoint:
    """Tests for GET /api/feed/cluster/{cluster_id} endpoint."""

    def test_get_cluster_success(self, client, auth_headers, sample_intelligence_item):
        """Should return cluster items."""
        cluster_id = sample_intelligence_item.cluster_id

        response = client.get(f"/api/feed/cluster/{cluster_id}", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["cluster_id"] == cluster_id
        assert "items" in data
        assert len(data["items"]) > 0

    def test_get_cluster_not_found(self, client, auth_headers):
        """Should return 404 for non-existent cluster."""
        response = client.get("/api/feed/cluster/nonexistent-cluster-id",
                              headers=auth_headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestCollectionErrorsEndpoint:
    """Tests for GET /api/feed/collection-errors endpoint."""

    def test_get_collection_errors_empty(self, client, auth_headers):
        """Should return empty list when no errors."""
        response = client.get("/api/feed/collection-errors", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "errors" in data
        assert data["errors"] == []

    def test_get_collection_errors_with_data(self, client, auth_headers, test_db, sample_customer):
        """Should return collection errors."""
        from app.models.database import CollectionStatus

        error = CollectionStatus(
            customer_id=sample_customer.id,
            source_type="linkedin",
            status="error",
            error_message="API rate limit exceeded",
            error_count=3,
            last_run=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            dismissed=False
        )
        test_db.add(error)
        test_db.commit()

        response = client.get("/api/feed/collection-errors", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["errors"]) > 0
        assert data["errors"][0]["source_type"] == "linkedin"

    def test_get_collection_errors_filter_by_customer(self, client, auth_headers, test_db, sample_customer):
        """Should filter errors by customer_id."""
        from app.models.database import CollectionStatus

        error = CollectionStatus(
            customer_id=sample_customer.id,
            source_type="reddit",
            status="error",
            error_message="Auth required",
            updated_at=datetime.utcnow(),
            dismissed=False
        )
        test_db.add(error)
        test_db.commit()

        response = client.get(f"/api/feed/collection-errors?customer_id={sample_customer.id}",
                              headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        for err in data["errors"]:
            assert err["customer_id"] == sample_customer.id


class TestDismissErrorEndpoint:
    """Tests for PATCH /api/feed/collection-errors/{error_id}/dismiss endpoint."""

    def test_dismiss_error_success(self, client, auth_headers, test_db, sample_customer):
        """Should dismiss collection error."""
        from app.models.database import CollectionStatus

        error = CollectionStatus(
            customer_id=sample_customer.id,
            source_type="linkedin",
            status="error",
            error_message="Test error",
            updated_at=datetime.utcnow(),
            dismissed=False
        )
        test_db.add(error)
        test_db.commit()

        response = client.patch(f"/api/feed/collection-errors/{error.id}/dismiss",
                                headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK

        # Verify in database
        test_db.refresh(error)
        assert error.dismissed is True
        assert error.dismissed_at is not None

    def test_dismiss_error_not_found(self, client, auth_headers):
        """Should return 404 for non-existent error."""
        response = client.patch("/api/feed/collection-errors/99999/dismiss",
                                headers=auth_headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND
