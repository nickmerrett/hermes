"""Application configuration settings"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # API Keys
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    news_api_key: str = ""

    # Social Media API Keys
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "CustomerIntelligenceTool/1.0"

    twitter_bearer_token: str = ""

    github_token: str = ""

    youtube_api_key: str = ""

    # Mailsac (for newsletter monitoring via disposable inboxes)
    mailsac_api_key: str = ""

    # Gmail OAuth (for press release digest monitoring)
    google_client_id: str = ""
    google_client_secret: str = ""
    google_oauth_redirect_uri: str = "http://localhost:8000/api/gmail/oauth/callback"

    # Encryption (for storing OAuth tokens securely)
    encryption_key: str = ""  # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

    # JWT Authentication
    jwt_secret_key: str = ""  # Required - Generate with: openssl rand -hex 32
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440  # 24 hours
    jwt_refresh_token_expire_days: int = 7

    # Bootstrap admin account (created on first startup if no users exist)
    first_admin_email: str = ""
    first_admin_password: str = ""

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
    sql_echo: bool = False  # Log all SQL queries (very verbose, only for debugging)

    # Database
    database_path: str = "data/db/intelligence.db"
    chroma_path: str = "data/chroma"

    # Scheduler
    enable_scheduler: bool = True
    hourly_collection_enabled: bool = True
    daily_collection_enabled: bool = True
    daily_collection_hour: int = 10  # Hour (0-23) to run daily comprehensive collection

    # AI Processing - Legacy individual model configuration (backward compatible)
    ai_provider: str = "anthropic"  # Provider for premium model: anthropic or openai
    ai_model: str = "claude-sonnet-4-5-20250929"  # Model for daily summaries and complex tasks
    ai_model_tier: str = "frontier"  # Prompt complexity tier: "frontier" (Sonnet, GPT-4, Opus) or "small" (Haiku, GPT-3.5, local models)
    ai_provider_cheap: str = "anthropic"  # Provider for economy model: anthropic or openai
    ai_model_cheap: str = "claude-haiku-4-5-20251001"  # Cheaper model for entity extraction, filtering, article summaries
    ai_model_tier_cheap: str = "small"  # Prompt complexity tier for cheap model: "frontier" or "small"
    model_override_in_ui: bool = False  # Allow UI to override model settings from environment variables

    # Prompt Template System (RECOMMENDED - per-prompt model assignment)
    # If set, this overrides all individual model settings above
    # The YAML template defines all 7 prompts with their individual model assignments
    # Can be either a template name (e.g., "qwen3-4b") or absolute path (e.g., "/path/to/template.yaml")
    ai_prompt_template: str = ""  # Template name OR absolute path. Empty = use individual settings above

    # API Base URLs
    anthropic_api_base_url: str = "https://api.anthropic.com"  # Anthropic API base URL (can override for proxies)
    openai_base_url: str = "https://api.openai.com/v1"  # OpenAI API base URL (supports OpenAI, LM Studio, Ollama, etc.)

    # Other AI Settings
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
        protected_namespaces = ()  # Allow field names starting with "model_"


# Global settings instance
settings = Settings()
