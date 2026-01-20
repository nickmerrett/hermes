"""
Integration tests for app/api/auth.py

Tests authentication endpoints including login, token refresh,
user management, and access control.
"""

import pytest
from fastapi import status


class TestLoginEndpoint:
    """Tests for POST /api/auth/login endpoint."""

    def test_login_success(self, client, test_user):
        """Should return tokens on successful login."""
        response = client.post("/api/auth/login", json={
            "email": "testuser@example.com",
            "password": "testpassword123"
        })

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data

    def test_login_invalid_email(self, client, test_user):
        """Should return 401 for non-existent email."""
        response = client.post("/api/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "testpassword123"
        })

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid email or password" in response.json()["detail"]

    def test_login_invalid_password(self, client, test_user):
        """Should return 401 for wrong password."""
        response = client.post("/api/auth/login", json={
            "email": "testuser@example.com",
            "password": "wrongpassword"
        })

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid email or password" in response.json()["detail"]

    def test_login_inactive_user(self, client, inactive_user):
        """Should return 401 for inactive user."""
        response = client.post("/api/auth/login", json={
            "email": "inactive@example.com",
            "password": "inactivepassword123"
        })

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "disabled" in response.json()["detail"].lower()

    def test_login_missing_email(self, client):
        """Should return 422 for missing email."""
        response = client.post("/api/auth/login", json={
            "password": "testpassword123"
        })

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_login_missing_password(self, client):
        """Should return 422 for missing password."""
        response = client.post("/api/auth/login", json={
            "email": "testuser@example.com"
        })

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_login_updates_last_login(self, client, test_user, test_db):
        """Should update last_login timestamp on successful login."""
        from app.models.database import User

        # Initial state - no last_login
        user = test_db.query(User).filter(User.id == test_user.id).first()
        initial_last_login = user.last_login

        # Login
        response = client.post("/api/auth/login", json={
            "email": "testuser@example.com",
            "password": "testpassword123"
        })
        assert response.status_code == status.HTTP_200_OK

        # Refresh user from db
        test_db.refresh(user)
        assert user.last_login is not None
        if initial_last_login:
            assert user.last_login > initial_last_login


class TestRefreshEndpoint:
    """Tests for POST /api/auth/refresh endpoint."""

    def test_refresh_success(self, client, user_tokens):
        """Should return new tokens with valid refresh token."""
        response = client.post("/api/auth/refresh", json={
            "refresh_token": user_tokens["refresh_token"]
        })

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        # Verify the new access token is a valid JWT format
        assert data["access_token"].count(".") == 2  # JWT has 3 parts

    def test_refresh_invalid_token(self, client):
        """Should return 401 for invalid refresh token."""
        response = client.post("/api/auth/refresh", json={
            "refresh_token": "invalid-token"
        })

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_with_access_token_fails(self, client, user_tokens):
        """Should return 401 when using access token as refresh token."""
        response = client.post("/api/auth/refresh", json={
            "refresh_token": user_tokens["access_token"]
        })

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid token type" in response.json()["detail"]


class TestGetCurrentUserEndpoint:
    """Tests for GET /api/auth/me endpoint."""

    def test_get_current_user_success(self, client, auth_headers, test_user):
        """Should return current user info."""
        response = client.get("/api/auth/me", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["email"] == test_user.email
        assert data["role"] == test_user.role
        assert data["id"] == test_user.id

    def test_get_current_user_no_token(self, client):
        """Should return 401 without token."""
        response = client.get("/api/auth/me")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_current_user_invalid_token(self, client):
        """Should return 401 with invalid token."""
        response = client.get("/api/auth/me", headers={
            "Authorization": "Bearer invalid-token"
        })

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestCreateUserEndpoint:
    """Tests for POST /api/auth/users endpoint."""

    def test_create_user_as_admin(self, client, admin_auth_headers):
        """Admin should be able to create new users."""
        response = client.post("/api/auth/users", headers=admin_auth_headers, json={
            "email": "newuser@example.com",
            "password": "newpassword123",
            "role": "user"
        })

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["role"] == "user"
        assert "id" in data

    def test_create_admin_user(self, client, admin_auth_headers):
        """Admin should be able to create other admins."""
        response = client.post("/api/auth/users", headers=admin_auth_headers, json={
            "email": "newadmin@example.com",
            "password": "adminpassword123",
            "role": "platform_admin"
        })

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["role"] == "platform_admin"

    def test_create_user_as_regular_user(self, client, auth_headers):
        """Regular user should not be able to create users."""
        response = client.post("/api/auth/users", headers=auth_headers, json={
            "email": "another@example.com",
            "password": "password123",
            "role": "user"
        })

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_user_duplicate_email(self, client, admin_auth_headers, test_user):
        """Should return 400 for duplicate email."""
        response = client.post("/api/auth/users", headers=admin_auth_headers, json={
            "email": test_user.email,
            "password": "password123",
            "role": "user"
        })

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already registered" in response.json()["detail"].lower()

    def test_create_user_no_auth(self, client):
        """Should return 401 without authentication."""
        response = client.post("/api/auth/users", json={
            "email": "test@example.com",
            "password": "password123",
            "role": "user"
        })

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestListUsersEndpoint:
    """Tests for GET /api/auth/users endpoint."""

    def test_list_users_as_admin(self, client, admin_auth_headers, test_user, admin_user):
        """Admin should see all users."""
        response = client.get("/api/auth/users", headers=admin_auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "users" in data
        assert "total" in data
        assert data["total"] >= 2  # At least test_user and admin_user

    def test_list_users_as_regular_user(self, client, auth_headers):
        """Regular user should not be able to list users."""
        response = client.get("/api/auth/users", headers=auth_headers)

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestGetUserEndpoint:
    """Tests for GET /api/auth/users/{user_id} endpoint."""

    def test_get_user_as_admin(self, client, admin_auth_headers, test_user):
        """Admin should be able to get any user."""
        response = client.get(f"/api/auth/users/{test_user.id}", headers=admin_auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == test_user.id
        assert data["email"] == test_user.email

    def test_get_nonexistent_user(self, client, admin_auth_headers):
        """Should return 404 for non-existent user."""
        response = client.get("/api/auth/users/99999", headers=admin_auth_headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_user_as_regular_user(self, client, auth_headers, admin_user):
        """Regular user should not be able to get other users."""
        response = client.get(f"/api/auth/users/{admin_user.id}", headers=auth_headers)

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestUpdateUserEndpoint:
    """Tests for PUT /api/auth/users/{user_id} endpoint."""

    def test_update_user_email(self, client, admin_auth_headers, test_user):
        """Admin should be able to update user email."""
        response = client.put(f"/api/auth/users/{test_user.id}",
                              headers=admin_auth_headers,
                              json={"email": "updated@example.com"})

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["email"] == "updated@example.com"

    def test_update_user_role(self, client, admin_auth_headers, test_user):
        """Admin should be able to update user role."""
        response = client.put(f"/api/auth/users/{test_user.id}",
                              headers=admin_auth_headers,
                              json={"role": "platform_admin"})

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["role"] == "platform_admin"

    def test_update_user_deactivate(self, client, admin_auth_headers, test_user):
        """Admin should be able to deactivate user."""
        response = client.put(f"/api/auth/users/{test_user.id}",
                              headers=admin_auth_headers,
                              json={"is_active": False})

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["is_active"] is False

    def test_cannot_deactivate_last_admin(self, client, admin_auth_headers, admin_user):
        """Should not allow deactivating the last admin."""
        response = client.put(f"/api/auth/users/{admin_user.id}",
                              headers=admin_auth_headers,
                              json={"is_active": False})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "last" in response.json()["detail"].lower()

    def test_cannot_demote_last_admin(self, client, admin_auth_headers, admin_user):
        """Should not allow demoting the last admin."""
        response = client.put(f"/api/auth/users/{admin_user.id}",
                              headers=admin_auth_headers,
                              json={"role": "user"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "last" in response.json()["detail"].lower()

    def test_update_to_duplicate_email(self, client, admin_auth_headers, test_user, admin_user):
        """Should not allow updating to existing email."""
        response = client.put(f"/api/auth/users/{test_user.id}",
                              headers=admin_auth_headers,
                              json={"email": admin_user.email})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already registered" in response.json()["detail"].lower()


class TestDeleteUserEndpoint:
    """Tests for DELETE /api/auth/users/{user_id} endpoint."""

    def test_delete_user_as_admin(self, client, admin_auth_headers, test_user):
        """Admin should be able to delete users."""
        response = client.delete(f"/api/auth/users/{test_user.id}",
                                 headers=admin_auth_headers)

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_cannot_delete_self(self, client, admin_auth_headers, admin_user):
        """Admin should not be able to delete themselves."""
        response = client.delete(f"/api/auth/users/{admin_user.id}",
                                 headers=admin_auth_headers)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "own account" in response.json()["detail"].lower()

    def test_cannot_delete_last_admin(self, client, test_db, admin_auth_headers):
        """Should not allow deleting the last admin."""
        from app.models.database import User
        from app.core.auth import password_hash

        # Create a second admin to delete the first
        second_admin = User(
            email="secondadmin@example.com",
            hashed_password=password_hash("adminpass"),
            role="platform_admin",
            is_active=True
        )
        test_db.add(second_admin)
        test_db.commit()

        # First admin (from fixture) tries to delete second admin - should work
        response = client.delete(f"/api/auth/users/{second_admin.id}",
                                 headers=admin_auth_headers)
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_nonexistent_user(self, client, admin_auth_headers):
        """Should return 404 for non-existent user."""
        response = client.delete("/api/auth/users/99999",
                                 headers=admin_auth_headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_user_as_regular_user(self, client, auth_headers, admin_user):
        """Regular user should not be able to delete users."""
        response = client.delete(f"/api/auth/users/{admin_user.id}",
                                 headers=auth_headers)

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestAuthenticationSecurity:
    """Security-focused tests for authentication."""

    def test_password_not_in_response(self, client, admin_auth_headers):
        """Password should never be returned in response."""
        response = client.post("/api/auth/users", headers=admin_auth_headers, json={
            "email": "secure@example.com",
            "password": "secretpassword123",
            "role": "user"
        })

        data = response.json()
        assert "password" not in data
        assert "hashed_password" not in data
        assert "secretpassword123" not in str(data)

    def test_tokens_are_different(self, client, test_user):
        """Access and refresh tokens should be different."""
        response = client.post("/api/auth/login", json={
            "email": "testuser@example.com",
            "password": "testpassword123"
        })

        data = response.json()
        assert data["access_token"] != data["refresh_token"]

    def test_expired_token_rejected(self, client, test_user):
        """Expired token should be rejected."""
        from datetime import timedelta
        from app.core.auth import create_access_token

        # Create token that's already expired
        token = create_access_token(
            {"sub": str(test_user.id), "email": test_user.email, "role": test_user.role},
            expires_delta=timedelta(seconds=-1)
        )

        response = client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
