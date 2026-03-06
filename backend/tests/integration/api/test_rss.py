"""
Integration tests for app/api/rss.py

Tests RSS feed generation and token management endpoints.
"""

from fastapi import status


class TestRSSFeedEndpoint:
    """Tests for GET /api/rss/feed endpoint."""

    def test_get_feed_with_valid_token(self, client, sample_rss_token, sample_intelligence_item):
        """Should return RSS XML with valid token."""
        response = client.get(f"/api/rss/feed?token={sample_rss_token.token}")

        assert response.status_code == status.HTTP_200_OK
        assert "application/rss+xml" in response.headers["content-type"]
        assert "<?xml" in response.text
        assert "<rss" in response.text

    def test_get_feed_invalid_token(self, client):
        """Should return 401 for invalid token."""
        response = client.get("/api/rss/feed?token=invalid-token-abc123")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid" in response.json()["detail"]

    def test_get_feed_missing_token(self, client):
        """Should return 422 for missing token."""
        response = client.get("/api/rss/feed")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_get_feed_inactive_token(self, client, test_db, sample_rss_token):
        """Should return 401 for inactive token."""
        # Deactivate the token
        sample_rss_token.is_active = False
        test_db.commit()

        response = client.get(f"/api/rss/feed?token={sample_rss_token.token}")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_feed_updates_last_used(self, client, test_db, sample_rss_token):
        """Should update last_used timestamp."""
        initial_last_used = sample_rss_token.last_used

        response = client.get(f"/api/rss/feed?token={sample_rss_token.token}")

        assert response.status_code == status.HTTP_200_OK

        test_db.refresh(sample_rss_token)
        assert sample_rss_token.last_used is not None
        if initial_last_used:
            assert sample_rss_token.last_used > initial_last_used

    def test_get_feed_contains_items(self, client, sample_rss_token, sample_intelligence_item):
        """RSS feed should contain intelligence items."""
        response = client.get(f"/api/rss/feed?token={sample_rss_token.token}")

        assert response.status_code == status.HTTP_200_OK
        # Check for item content in the XML
        assert "<item>" in response.text
        assert sample_intelligence_item.title in response.text

    def test_get_feed_has_channel_info(self, client, sample_rss_token, sample_customer):
        """RSS feed should have proper channel information."""
        response = client.get(f"/api/rss/feed?token={sample_rss_token.token}")

        assert response.status_code == status.HTTP_200_OK
        assert "<channel>" in response.text
        assert sample_customer.name in response.text


class TestListTokensEndpoint:
    """Tests for GET /api/rss/tokens endpoint."""

    def test_list_tokens_empty(self, client, auth_headers):
        """Should return empty list when user has no tokens."""
        response = client.get("/api/rss/tokens", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "tokens" in data
        assert "total" in data

    def test_list_tokens_with_data(self, client, auth_headers, sample_rss_token):
        """Should return user's tokens."""
        response = client.get("/api/rss/tokens", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["tokens"]) > 0
        assert data["total"] >= 1

    def test_list_tokens_only_own_tokens(self, client, admin_auth_headers, sample_rss_token):
        """User should only see their own tokens."""
        # sample_rss_token belongs to test_user, not admin_user
        response = client.get("/api/rss/tokens", headers=admin_auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Admin shouldn't see test_user's token
        token_ids = [t["id"] for t in data["tokens"]]
        assert sample_rss_token.id not in token_ids

    def test_list_tokens_no_auth(self, client):
        """Should return 401 without authentication."""
        response = client.get("/api/rss/tokens")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_tokens_includes_customer_name(self, client, auth_headers, sample_rss_token, sample_customer):
        """Token response should include customer name."""
        response = client.get("/api/rss/tokens", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        token = next(t for t in data["tokens"] if t["id"] == sample_rss_token.id)
        assert token["customer_name"] == sample_customer.name


class TestCreateTokenEndpoint:
    """Tests for POST /api/rss/tokens endpoint."""

    def test_create_token_success(self, client, auth_headers, sample_customer):
        """Should create new RSS token."""
        response = client.post("/api/rss/tokens", headers=auth_headers, json={
            "name": "My Feed Token",
            "customer_id": sample_customer.id
        })

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "My Feed Token"
        assert data["customer_id"] == sample_customer.id
        assert "token" in data
        assert len(data["token"]) > 20  # Token should be reasonably long

    def test_create_token_includes_rss_url(self, client, auth_headers, sample_customer):
        """Created token should include RSS URL."""
        response = client.post("/api/rss/tokens", headers=auth_headers, json={
            "name": "URL Test Token",
            "customer_id": sample_customer.id
        })

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "rss_url" in data
        assert "/api/rss/feed?token=" in data["rss_url"]

    def test_create_token_invalid_customer(self, client, auth_headers):
        """Should return 404 for non-existent customer."""
        response = client.post("/api/rss/tokens", headers=auth_headers, json={
            "name": "Invalid Customer Token",
            "customer_id": 99999
        })

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_token_no_auth(self, client, sample_customer):
        """Should return 401 without authentication."""
        response = client.post("/api/rss/tokens", json={
            "name": "Unauthorized Token",
            "customer_id": sample_customer.id
        })

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_token_is_active_by_default(self, client, auth_headers, sample_customer):
        """Created token should be active by default."""
        response = client.post("/api/rss/tokens", headers=auth_headers, json={
            "name": "Active Token",
            "customer_id": sample_customer.id
        })

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["is_active"] is True


class TestRevokeTokenEndpoint:
    """Tests for DELETE /api/rss/tokens/{token_id} endpoint."""

    def test_revoke_own_token(self, client, auth_headers, sample_rss_token, test_db):
        """User should be able to revoke their own token."""
        token_id = sample_rss_token.id

        response = client.delete(f"/api/rss/tokens/{token_id}", headers=auth_headers)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify deletion
        from app.models.database import RSSFeedToken
        deleted = test_db.query(RSSFeedToken).filter(RSSFeedToken.id == token_id).first()
        assert deleted is None

    def test_revoke_other_user_token_as_regular_user(self, client, test_db, sample_customer, admin_user):
        """Regular user should not be able to revoke other's tokens."""
        from app.models.database import RSSFeedToken
        from app.core.auth import create_access_token

        # Create token for admin user
        admin_token = RSSFeedToken(
            token="admin-token-123",
            customer_id=sample_customer.id,
            user_id=admin_user.id,
            name="Admin's Token",
            is_active=True
        )
        test_db.add(admin_token)
        test_db.commit()

        # Try to delete as regular user
        regular_user_auth = {"Authorization": f"Bearer {create_access_token({'sub': '999', 'email': 'other@test.com', 'role': 'user'})}"}

        response = client.delete(f"/api/rss/tokens/{admin_token.id}", headers=regular_user_auth)

        # Should be forbidden or not found
        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED]

    def test_revoke_other_user_token_as_admin(self, client, admin_auth_headers, sample_rss_token, test_db):
        """Admin should be able to revoke any token."""
        token_id = sample_rss_token.id

        response = client.delete(f"/api/rss/tokens/{token_id}", headers=admin_auth_headers)

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_revoke_nonexistent_token(self, client, auth_headers):
        """Should return 404 for non-existent token."""
        response = client.delete("/api/rss/tokens/99999", headers=auth_headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestDeactivateTokenEndpoint:
    """Tests for PATCH /api/rss/tokens/{token_id}/deactivate endpoint."""

    def test_deactivate_token(self, client, auth_headers, sample_rss_token, test_db):
        """Should deactivate token without deleting it."""
        response = client.patch(f"/api/rss/tokens/{sample_rss_token.id}/deactivate",
                                headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK

        test_db.refresh(sample_rss_token)
        assert sample_rss_token.is_active is False

    def test_deactivate_nonexistent_token(self, client, auth_headers):
        """Should return 404 for non-existent token."""
        response = client.patch("/api/rss/tokens/99999/deactivate", headers=auth_headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_deactivate_other_user_token(self, client, admin_auth_headers, sample_rss_token, test_db):
        """Admin should be able to deactivate any token."""
        response = client.patch(f"/api/rss/tokens/{sample_rss_token.id}/deactivate",
                                headers=admin_auth_headers)

        assert response.status_code == status.HTTP_200_OK


class TestActivateTokenEndpoint:
    """Tests for PATCH /api/rss/tokens/{token_id}/activate endpoint."""

    def test_activate_token(self, client, auth_headers, sample_rss_token, test_db):
        """Should activate a deactivated token."""
        # First deactivate
        sample_rss_token.is_active = False
        test_db.commit()

        response = client.patch(f"/api/rss/tokens/{sample_rss_token.id}/activate",
                                headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK

        test_db.refresh(sample_rss_token)
        assert sample_rss_token.is_active is True

    def test_activate_nonexistent_token(self, client, auth_headers):
        """Should return 404 for non-existent token."""
        response = client.patch("/api/rss/tokens/99999/activate", headers=auth_headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestGetCustomerFeedSettings:
    """Tests for GET /api/rss/settings/{customer_id} endpoint."""

    def test_get_settings_success(self, client, auth_headers, sample_customer):
        """Should return customer feed settings."""
        response = client.get(f"/api/rss/settings/{sample_customer.id}",
                              headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["customer_id"] == sample_customer.id
        assert "effective_settings" in data
        assert "global_settings" in data
        assert "defaults" in data

    def test_get_settings_customer_not_found(self, client, auth_headers):
        """Should return 404 for non-existent customer."""
        response = client.get("/api/rss/settings/99999", headers=auth_headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_settings_no_auth(self, client, sample_customer):
        """Should return 401 without authentication."""
        response = client.get(f"/api/rss/settings/{sample_customer.id}")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_settings_with_custom_config(self, client, auth_headers, sample_customer_with_custom_feed):
        """Should show custom settings when configured."""
        response = client.get(f"/api/rss/settings/{sample_customer_with_custom_feed.id}",
                              headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["use_custom"] is True
        assert data["customer_settings"]["min_priority"] == 0.5


class TestUpdateCustomerFeedSettings:
    """Tests for PUT /api/rss/settings/{customer_id} endpoint."""

    def test_update_settings_success(self, client, auth_headers, sample_customer, test_db):
        """Should update customer feed settings."""
        response = client.put(f"/api/rss/settings/{sample_customer.id}",
                              headers=auth_headers,
                              json={
                                  "use_custom": True,
                                  "min_priority": 0.4,
                                  "max_items": 30
                              })

        assert response.status_code == status.HTTP_200_OK

        # Verify in database
        test_db.refresh(sample_customer)
        assert sample_customer.config["smart_feed"]["use_custom"] is True
        assert sample_customer.config["smart_feed"]["min_priority"] == 0.4

    def test_update_settings_customer_not_found(self, client, auth_headers):
        """Should return 404 for non-existent customer."""
        response = client.put("/api/rss/settings/99999",
                              headers=auth_headers,
                              json={"use_custom": True})

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_settings_no_auth(self, client, sample_customer):
        """Should return 401 without authentication."""
        response = client.put(f"/api/rss/settings/{sample_customer.id}",
                              json={"use_custom": True})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_update_settings_enables_custom(self, client, auth_headers, sample_customer, test_db):
        """Should enable custom settings for customer."""
        response = client.put(f"/api/rss/settings/{sample_customer.id}",
                              headers=auth_headers,
                              json={
                                  "use_custom": True,
                                  "category_preferences": {
                                      "financial": True,
                                      "competitor": False
                                  }
                              })

        assert response.status_code == status.HTTP_200_OK

        # Verify settings are applied
        get_response = client.get(f"/api/rss/settings/{sample_customer.id}",
                                  headers=auth_headers)
        data = get_response.json()
        assert data["use_custom"] is True


class TestRSSFeedContent:
    """Tests for RSS feed content and format."""

    def test_feed_is_valid_rss(self, client, sample_rss_token, sample_intelligence_item):
        """Feed should be valid RSS 2.0."""
        response = client.get(f"/api/rss/feed?token={sample_rss_token.token}")

        assert response.status_code == status.HTTP_200_OK
        content = response.text

        # Check RSS 2.0 structure
        assert '<?xml version="1.0"' in content
        assert '<rss' in content and 'version="2.0"' in content
        assert '<channel>' in content
        assert '</channel>' in content
        assert '</rss>' in content

    def test_feed_items_have_required_elements(self, client, sample_rss_token, sample_intelligence_item):
        """Feed items should have required RSS elements."""
        response = client.get(f"/api/rss/feed?token={sample_rss_token.token}")

        assert response.status_code == status.HTTP_200_OK
        content = response.text

        # Items should have title, link, description
        assert '<title>' in content
        assert '<link>' in content

    def test_feed_excludes_ignored_items(self, client, sample_rss_token, test_db, sample_customer):
        """Feed should not include ignored items."""
        from app.models.database import IntelligenceItem
        from datetime import datetime

        # Create an ignored item
        ignored = IntelligenceItem(
            customer_id=sample_customer.id,
            source_type="rss",
            title="IGNORED_ITEM_TITLE",
            url="https://example.com/ignored",
            is_cluster_primary=True,
            ignored=True,
            ignored_at=datetime.utcnow()
        )
        test_db.add(ignored)
        test_db.commit()

        response = client.get(f"/api/rss/feed?token={sample_rss_token.token}")

        assert response.status_code == status.HTTP_200_OK
        assert "IGNORED_ITEM_TITLE" not in response.text
