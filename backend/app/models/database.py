"""SQLAlchemy database models"""

from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean,
    DateTime, JSON, ForeignKey, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class Customer(Base):
    """Customer/company to monitor"""
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    domain = Column(String(255))
    keywords = Column(JSON)  # List of keywords to search
    competitors = Column(JSON)  # List of competitor names
    stock_symbol = Column(String(10))
    tab_color = Column(String(7), default='#ffffff')  # Hex color for tab background
    config = Column(JSON)  # Additional configuration
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sources = relationship("Source", back_populates="customer", cascade="all, delete-orphan")
    intelligence_items = relationship("IntelligenceItem", back_populates="customer", cascade="all, delete-orphan")


class Source(Base):
    """Data source configuration"""
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    type = Column(String(50), nullable=False)  # 'news_api', 'rss', 'stock', etc.
    name = Column(String(255), nullable=False)
    url = Column(String(1024))
    config = Column(JSON)  # Source-specific configuration
    last_run = Column(DateTime)
    last_status = Column(String(50))  # 'success', 'failed', 'running'
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    customer = relationship("Customer", back_populates="sources")
    intelligence_items = relationship("IntelligenceItem", back_populates="source")


class IntelligenceItem(Base):
    """Raw intelligence item collected from a source"""
    __tablename__ = "intelligence_items"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    source_id = Column(Integer, ForeignKey("sources.id"))
    source_type = Column(String(50), nullable=False, index=True)
    title = Column(Text, nullable=False)
    content = Column(Text)
    url = Column(String(2048), unique=True, index=True)
    published_date = Column(DateTime, index=True)
    collected_date = Column(DateTime, default=datetime.utcnow, index=True)
    raw_data = Column(JSON)  # Store original data for debugging

    # Story clustering fields
    cluster_id = Column(String(36), nullable=True, index=True)  # UUID for story clusters
    is_cluster_primary = Column(Boolean, default=False, index=True)  # Is this the primary/representative item?
    source_tier = Column(String(20), nullable=True)  # official/primary/secondary/aggregator/social
    cluster_member_count = Column(Integer, default=1)  # How many items in this cluster (denormalized for performance)

    # User actions
    ignored = Column(Boolean, default=False, index=True)  # User has ignored/dismissed this item
    ignored_at = Column(DateTime, nullable=True)  # When item was ignored

    # Relationships
    customer = relationship("Customer", back_populates="intelligence_items")
    source = relationship("Source", back_populates="intelligence_items")
    processed = relationship("ProcessedIntelligence", back_populates="item", uselist=False, cascade="all, delete-orphan")


class ProcessedIntelligence(Base):
    """AI-processed intelligence with summarization and classification"""
    __tablename__ = "processed_intelligence"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("intelligence_items.id"), unique=True, nullable=False)
    summary = Column(Text)
    category = Column(String(100), index=True)
    sentiment = Column(String(50), index=True)  # 'positive', 'negative', 'neutral', 'mixed'
    priority_score = Column(Float, default=0.5, index=True)  # 0.0 to 1.0
    entities = Column(JSON)  # Extracted entities (people, companies, technologies)
    tags = Column(JSON)  # Generated tags
    processed_date = Column(DateTime, default=datetime.utcnow)

    # AI processing status tracking
    needs_reprocessing = Column(Boolean, default=False, index=True)  # True if AI processing failed
    processing_attempts = Column(Integer, default=0)  # Number of times processing was attempted
    last_processing_error = Column(Text)  # Last error message from AI processing
    last_processing_attempt = Column(DateTime)  # When last processing was attempted

    # Relationships
    item = relationship("IntelligenceItem", back_populates="processed")


class CollectionJob(Base):
    """Track collection job execution"""
    __tablename__ = "collection_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_type = Column(String(100), nullable=False)  # 'hourly_news', 'daily_comprehensive', etc.
    customer_id = Column(Integer, ForeignKey("customers.id"))
    source_id = Column(Integer, ForeignKey("sources.id"))
    status = Column(String(50), nullable=False, index=True)  # 'pending', 'running', 'completed', 'failed'
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    items_collected = Column(Integer, default=0)
    items_failed_processing = Column(Integer, default=0)  # Items that failed AI processing
    error_message = Column(Text)

    __table_args__ = (
        UniqueConstraint('job_type', 'started_at', name='uix_job_started'),
    )


class DailySummary(Base):
    """Cached AI-generated daily summaries"""
    __tablename__ = "daily_summaries"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    summary_date = Column(DateTime, nullable=False, index=True)  # The date this summary covers
    summary_text = Column(Text, nullable=False)  # AI-generated executive summary
    total_items = Column(Integer, default=0)
    high_priority_count = Column(Integer, default=0)
    items_by_category = Column(JSON)  # Category breakdown
    generated_at = Column(DateTime, default=datetime.utcnow, index=True)  # When this was generated

    __table_args__ = (
        UniqueConstraint('customer_id', 'summary_date', name='uix_customer_summary_date'),
    )


class CollectionStatus(Base):
    """Track current collection status per source type per customer"""
    __tablename__ = "collection_status"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    source_type = Column(String(50), nullable=False, index=True)  # 'reddit', 'linkedin_user', etc.
    status = Column(String(50), nullable=False, index=True)  # 'success', 'error', 'auth_required'
    last_run = Column(DateTime, index=True)
    last_success = Column(DateTime)  # Last time this collector succeeded
    error_message = Column(Text)
    error_count = Column(Integer, default=0)  # Consecutive failures
    dismissed = Column(Boolean, default=False, index=True)  # User has dismissed this error
    dismissed_at = Column(DateTime, nullable=True)  # When error was dismissed
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('customer_id', 'source_type', name='uix_customer_source_type'),
    )


class PlatformSettings(Base):
    """Platform-wide configuration settings"""
    __tablename__ = "platform_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), unique=True, nullable=False, index=True)  # 'daily_briefing', 'ai_config', etc.
    value = Column(JSON, nullable=False)  # JSON configuration
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
