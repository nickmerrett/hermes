"""
Shared pytest fixtures for Hermes test suite.

This module provides common fixtures used across unit and integration tests:
- Database fixtures for integration tests (in-memory SQLite)
- FastAPI test client with database override
- Authentication fixtures (users, tokens)
- Sample data fixtures (customers, intelligence items)
"""

import pytest
import os
from datetime import datetime, timedelta
from typing import Generator

# Set test environment before importing app modules
os.environ["TESTING"] = "true"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["JWT_ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["JWT_REFRESH_TOKEN_EXPIRE_DAYS"] = "7"
# Generate a valid Fernet key for testing (must be 32 url-safe base64-encoded bytes)
from cryptography.fernet import Fernet
os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

from app.models.database import Base, User, Customer, IntelligenceItem, ProcessedIntelligence, RSSFeedToken
from app.core.database import get_db
from app.core.auth import password_hash, create_access_token, create_refresh_token
from app.main import app


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def test_engine():
    """Create an in-memory SQLite database engine for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Create all tables
    Base.metadata.create_all(bind=engine)
    yield engine
    # Cleanup
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_db(test_engine) -> Generator[Session, None, None]:
    """Create a test database session."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def client(test_db) -> Generator[TestClient, None, None]:
    """Create a FastAPI test client with database override."""
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ============================================================================
# User Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def test_user(test_db) -> User:
    """Create a regular test user."""
    user = User(
        email="testuser@example.com",
        hashed_password=password_hash("testpassword123"),
        role="user",
        is_active=True,
        created_at=datetime.utcnow()
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture(scope="function")
def admin_user(test_db) -> User:
    """Create an admin test user."""
    user = User(
        email="admin@example.com",
        hashed_password=password_hash("adminpassword123"),
        role="platform_admin",
        is_active=True,
        created_at=datetime.utcnow()
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture(scope="function")
def inactive_user(test_db) -> User:
    """Create an inactive test user."""
    user = User(
        email="inactive@example.com",
        hashed_password=password_hash("inactivepassword123"),
        role="user",
        is_active=False,
        created_at=datetime.utcnow()
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


# ============================================================================
# Authentication Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def auth_headers(test_user) -> dict:
    """Create authentication headers for a regular user."""
    token_data = {
        "sub": str(test_user.id),
        "email": test_user.email,
        "role": test_user.role
    }
    access_token = create_access_token(token_data)
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture(scope="function")
def admin_auth_headers(admin_user) -> dict:
    """Create authentication headers for an admin user."""
    token_data = {
        "sub": str(admin_user.id),
        "email": admin_user.email,
        "role": admin_user.role
    }
    access_token = create_access_token(token_data)
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture(scope="function")
def user_tokens(test_user) -> dict:
    """Create both access and refresh tokens for a test user."""
    token_data = {
        "sub": str(test_user.id),
        "email": test_user.email,
        "role": test_user.role
    }
    return {
        "access_token": create_access_token(token_data),
        "refresh_token": create_refresh_token(token_data)
    }


# ============================================================================
# Customer Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def sample_customer(test_db) -> Customer:
    """Create a sample customer for testing."""
    customer = Customer(
        name="Acme Corporation",
        domain="acme.com",
        keywords=["acme", "widgets", "innovation"],
        competitors=["GlobalCorp", "MegaTech"],
        stock_symbol="ACME",
        tab_color="#3498db",
        config={
            "smart_feed": {
                "use_custom": False
            }
        },
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    test_db.add(customer)
    test_db.commit()
    test_db.refresh(customer)
    return customer


@pytest.fixture(scope="function")
def sample_customer_with_custom_feed(test_db) -> Customer:
    """Create a customer with custom smart feed settings."""
    customer = Customer(
        name="Custom Corp",
        domain="customcorp.com",
        keywords=["custom", "specialized"],
        competitors=[],
        stock_symbol="CUST",
        tab_color="#e74c3c",
        config={
            "smart_feed": {
                "use_custom": True,
                "min_priority": 0.5,
                "max_items": 25,
                "category_preferences": {
                    "financial": True,
                    "competitor": True
                }
            }
        },
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    test_db.add(customer)
    test_db.commit()
    test_db.refresh(customer)
    return customer


# ============================================================================
# Intelligence Item Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def sample_intelligence_item(test_db, sample_customer) -> IntelligenceItem:
    """Create a sample intelligence item with processed data."""
    item = IntelligenceItem(
        customer_id=sample_customer.id,
        source_type="rss",
        title="Acme Corp Announces New Product Line",
        content="Acme Corporation today announced a revolutionary new product line that will transform the industry.",
        url="https://news.example.com/acme-new-product",
        published_date=datetime.utcnow() - timedelta(hours=2),
        collected_date=datetime.utcnow() - timedelta(hours=1),
        cluster_id="cluster-001",
        is_cluster_primary=True,
        source_tier="primary",
        cluster_member_count=1,
        ignored=False
    )
    test_db.add(item)
    test_db.commit()
    test_db.refresh(item)

    # Add processed intelligence
    processed = ProcessedIntelligence(
        item_id=item.id,
        summary="Acme announces new innovative product line.",
        category="product_update",
        sentiment="positive",
        priority_score=0.8,
        entities={"companies": ["Acme Corporation"], "products": ["new product line"]},
        tags=["product", "announcement", "innovation"],
        pain_points_opportunities={
            "pain_points": [],
            "opportunities": ["Market expansion opportunity"]
        },
        processed_date=datetime.utcnow()
    )
    test_db.add(processed)
    test_db.commit()

    # Refresh to get the relationship loaded
    test_db.refresh(item)
    return item


@pytest.fixture(scope="function")
def sample_intelligence_items(test_db, sample_customer) -> list:
    """Create multiple intelligence items for testing feeds."""
    items = []
    categories = ["financial", "competitor", "product_update", "leadership"]
    sources = ["rss", "linkedin", "press_release", "news_api"]

    for i, (category, source) in enumerate(zip(categories, sources)):
        item = IntelligenceItem(
            customer_id=sample_customer.id,
            source_type=source,
            title=f"Test Article {i+1}: {category.title()} News",
            content=f"This is test content for article {i+1} about {category}.",
            url=f"https://news.example.com/article-{i+1}",
            published_date=datetime.utcnow() - timedelta(hours=i*2),
            collected_date=datetime.utcnow() - timedelta(hours=i*2-1),
            cluster_id=f"cluster-{i+1:03d}",
            is_cluster_primary=True,
            source_tier="primary" if source in ["linkedin", "press_release"] else "secondary",
            cluster_member_count=1,
            ignored=False
        )
        test_db.add(item)
        test_db.commit()
        test_db.refresh(item)

        # Add processed intelligence
        processed = ProcessedIntelligence(
            item_id=item.id,
            summary=f"Summary for article {i+1}",
            category=category,
            sentiment="positive" if i % 2 == 0 else "neutral",
            priority_score=0.9 - (i * 0.15),  # Varying priorities
            entities={"companies": [sample_customer.name]},
            tags=[category, "test"],
            processed_date=datetime.utcnow()
        )
        test_db.add(processed)
        test_db.commit()

        test_db.refresh(item)
        items.append(item)

    return items


# ============================================================================
# RSS Token Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def sample_rss_token(test_db, test_user, sample_customer) -> RSSFeedToken:
    """Create a sample RSS token."""
    token = RSSFeedToken(
        token="test-rss-token-abc123",
        customer_id=sample_customer.id,
        user_id=test_user.id,
        name="Test RSS Feed",
        is_active=True,
        created_at=datetime.utcnow()
    )
    test_db.add(token)
    test_db.commit()
    test_db.refresh(token)
    return token


# ============================================================================
# Utility Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def mock_datetime():
    """Fixture for mocking datetime in tests."""
    return datetime(2024, 1, 15, 12, 0, 0)


@pytest.fixture(scope="session")
def encryption_key():
    """Provide a valid Fernet encryption key for testing."""
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode()
