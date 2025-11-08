"""Pydantic schemas for API request/response validation"""

from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class SentimentType(str, Enum):
    """Sentiment classification options"""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class CategoryType(str, Enum):
    """Intelligence item categories"""
    PRODUCT_UPDATE = "product_update"
    FINANCIAL = "financial"
    MARKET_NEWS = "market_news"
    COMPETITOR = "competitor"
    CHALLENGE = "challenge"
    OPPORTUNITY = "opportunity"
    LEADERSHIP = "leadership"
    PARTNERSHIP = "partnership"
    ADVERTISEMENT = "advertisement"
    UNRELATED = "unrelated"
    OTHER = "other"


class SourceType(str, Enum):
    """Data source types"""
    NEWS_API = "news_api"
    RSS = "rss"
    STOCK = "stock"
    LINKEDIN = "linkedin"
    TWITTER = "twitter"
    WEB_SCRAPE = "web_scrape"


# Customer Schemas
class CustomerBase(BaseModel):
    """Base customer schema"""
    name: str
    domain: Optional[str] = None
    keywords: List[str] = []
    competitors: List[str] = []
    stock_symbol: Optional[str] = None
    tab_color: Optional[str] = '#ffffff'
    config: Optional[Dict[str, Any]] = None


class CustomerCreate(CustomerBase):
    """Schema for creating a customer"""
    pass


class CustomerUpdate(BaseModel):
    """Schema for updating a customer"""
    name: Optional[str] = None
    domain: Optional[str] = None
    keywords: Optional[List[str]] = None
    competitors: Optional[List[str]] = None
    stock_symbol: Optional[str] = None
    tab_color: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class CustomerResponse(CustomerBase):
    """Schema for customer response"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Intelligence Item Schemas
class IntelligenceItemBase(BaseModel):
    """Base intelligence item schema"""
    title: str
    content: Optional[str] = None
    url: Optional[str] = None
    source_type: str
    published_date: Optional[datetime] = None


class IntelligenceItemCreate(IntelligenceItemBase):
    """Schema for creating an intelligence item"""
    customer_id: int
    source_id: Optional[int] = None
    raw_data: Optional[Dict[str, Any]] = None


class ProcessedIntelligenceResponse(BaseModel):
    """Schema for processed intelligence data"""
    summary: Optional[str] = None
    category: Optional[str] = None
    sentiment: Optional[str] = None
    priority_score: float = 0.5
    entities: Optional[Dict[str, List[str]]] = None
    tags: Optional[List[str]] = None
    processed_date: Optional[datetime] = None

    # AI processing status tracking
    needs_reprocessing: bool = False
    processing_attempts: int = 0
    last_processing_error: Optional[str] = None
    last_processing_attempt: Optional[datetime] = None

    class Config:
        from_attributes = True


class IntelligenceItemResponse(IntelligenceItemBase):
    """Schema for intelligence item response"""
    id: int
    customer_id: int
    source_id: Optional[int] = None
    collected_date: datetime
    processed: Optional[ProcessedIntelligenceResponse] = None

    # Story clustering fields
    cluster_id: Optional[str] = None
    is_cluster_primary: bool = False
    source_tier: Optional[str] = None
    cluster_member_count: int = 1

    class Config:
        from_attributes = True


class IntelligenceItemDetail(IntelligenceItemResponse):
    """Detailed intelligence item response including raw data"""
    raw_data: Optional[Dict[str, Any]] = None


# Feed Query Schema
class FeedQuery(BaseModel):
    """Query parameters for intelligence feed"""
    customer_id: Optional[int] = None
    category: Optional[str] = None
    sentiment: Optional[str] = None
    source_type: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    min_priority: Optional[float] = Field(None, ge=0.0, le=1.0)
    search: Optional[str] = None
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)


class FeedResponse(BaseModel):
    """Response for intelligence feed"""
    items: List[IntelligenceItemResponse]
    total: int
    limit: int
    offset: int
    clustered: bool = True  # Whether response shows clustered view


# Source Schemas
class SourceBase(BaseModel):
    """Base source schema"""
    type: str
    name: str
    url: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    enabled: bool = True


class SourceCreate(SourceBase):
    """Schema for creating a source"""
    customer_id: int


class SourceResponse(SourceBase):
    """Schema for source response"""
    id: int
    customer_id: int
    last_run: Optional[datetime] = None
    last_status: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Collection Job Schemas
class CollectionJobResponse(BaseModel):
    """Schema for collection job response"""
    id: int
    job_type: str
    customer_id: Optional[int] = None
    source_id: Optional[int] = None
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    items_collected: int
    items_failed_processing: int = 0
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


# Search Schema
class SemanticSearchQuery(BaseModel):
    """Query for semantic search"""
    query: str
    customer_id: Optional[int] = None
    limit: int = Field(10, ge=1, le=50)
    min_similarity: float = Field(0.3, ge=0.0, le=1.0)  # Lowered threshold for better recall


class SearchResult(BaseModel):
    """Search result with similarity score"""
    item: IntelligenceItemResponse
    similarity: float


class SearchResponse(BaseModel):
    """Response for search query"""
    results: List[SearchResult]
    query: str


# Analytics Schema
class AnalyticsSummary(BaseModel):
    """Analytics summary response"""
    total_items: int
    items_by_category: Dict[str, int]
    items_by_sentiment: Dict[str, int]
    items_by_source: Dict[str, int]
    recent_items_count: int  # Last 24 hours
    high_priority_items: int  # Priority > 0.7
    customers_monitored: int


# Health Check
class HealthCheck(BaseModel):
    """Health check response"""
    status: str
    version: str
    database: str
    scheduler: str
