"""Application configuration settings"""

from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # API Keys
    anthropic_api_key: str = ""
    news_api_key: str = ""

    # Social Media API Keys
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "CustomerIntelligenceTool/1.0"

    twitter_bearer_token: str = ""

    github_token: str = ""

    youtube_api_key: str = ""

    # Third-party services (optional)
    proxycurl_api_key: str = ""  # For LinkedIn data (deprecated)

    # API Base URLs (configurable for proxies/testing)
    hackernews_api_base_url: str = "https://hn.algolia.com/api/v1"
    linkedin_base_url: str = "https://www.linkedin.com"

    # LinkedIn Playwright Scraping (optional)
    linkedin_email: str = ""  # Your LinkedIn email for logged-in scraping
    linkedin_password: str = ""  # Your LinkedIn password
    linkedin_headless: bool = True  # Run browser in headless mode

    # Application
    app_env: str = "development"
    log_level: str = "INFO"

    # Database
    database_path: str = "data/db/intelligence.db"
    chroma_path: str = "data/chroma"

    # Scheduler
    enable_scheduler: bool = True
    hourly_collection_enabled: bool = True
    daily_collection_enabled: bool = True
    daily_collection_hour: int = 10  # Hour (0-23) to run daily comprehensive collection

    # AI Processing
    ai_model: str = "claude-sonnet-4-5-20250929"  # Claude model to use for processing (Claude Sonnet 4.5)
    ai_api_base_url: str = "https://api.anthropic.com"  # Anthropic API base URL (can override for proxies)
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    max_tokens_summary: int = 800  # Max tokens for AI summaries

    # API Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"

    # Rate Limiting
    news_api_rate_limit: int = 100
    claude_api_rate_limit: int = 50

    # Data Retention
    intelligence_retention_days: int = 90

    # Customer Config
    customers_config_path: str = "config/customers.yaml"

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins into a list"""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def database_url(self) -> str:
        """SQLite database URL"""
        return f"sqlite:///{self.database_path}"

    @property
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.app_env == "development"

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
