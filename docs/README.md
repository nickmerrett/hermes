# Hermes Documentation

Complete documentation for the Hermes intelligence platform.

## 📖 Table of Contents

### 🚀 Getting Started
- **[Main README](../README.md)** - Project overview, quick start, and installation
- **[Development Roadmap](../ROADMAP.md)** - Features, priorities, and implementation status

### 📊 Data Sources & Collectors
- **[Collector Overview](collectors/README.md)** - All available data sources and configuration
- **[YouTube Collector](collectors/YOUTUBE.md)** - YouTube Data API setup and channel monitoring

### 🏗️ Architecture & Technical Docs
- **[Collection Architecture](architecture/COLLECTION_ARCHITECTURE.md)** - Parallel collection, rate limiting, and scraping strategies

### 🛠️ Operations & Maintenance
- **[Diagnostics CLI](operations/DIAGNOSTICS.md)** - hermes-diag tool reference and troubleshooting
- **[Utility Tools](operations/TOOLS.md)** - Database migrations and maintenance scripts

## Quick Navigation

### For Users

**Setting Up Hermes:**
1. Follow [Quick Start](../README.md#quick-start) in main README
2. Configure customers via UI or YAML
3. Enable data sources per customer
4. Configure platform settings

**Data Collection:**
- [Enable YouTube monitoring](collectors/YOUTUBE.md) - Video content via transcripts
- [Configure collectors](collectors/README.md) - All available sources
- [Platform Settings](collectors/README.md#global-configuration-platform-settings) - Global collection settings

**Troubleshooting:**
- [Diagnostics CLI](operations/DIAGNOSTICS.md) - Debug collection issues
- [Collection errors](architecture/COLLECTION_ARCHITECTURE.md#error-handling) - Understanding error banners

### For Developers

**Understanding the System:**
- [Collection Architecture](architecture/COLLECTION_ARCHITECTURE.md) - How data collection works
- [Roadmap](../ROADMAP.md) - Feature status and upcoming work

**Development Tasks:**
- [Utility Tools](operations/TOOLS.md) - Database migrations and debugging
- [Adding New Collectors](collectors/README.md#adding-new-collectors) - Extend data sources
- [Rate Limiting](architecture/COLLECTION_ARCHITECTURE.md#global-rate-limiter) - API limits and strategies

**Maintenance:**
- [Diagnostics](operations/DIAGNOSTICS.md) - hermes-diag commands
- [Database Migrations](operations/TOOLS.md#database-migrations) - Schema updates
- [Vector Store Management](operations/TOOLS.md#vector-store-management) - ChromaDB operations

## Documentation Structure

```
docs/
├── README.md (this file)                  # Documentation index
│
├── architecture/
│   └── COLLECTION_ARCHITECTURE.md         # Parallel collection, rate limiting, scraping
│
├── collectors/
│   ├── README.md                          # All data sources overview
│   └── YOUTUBE_SETUP.md                   # YouTube setup guide
│
├── operations/
│   ├── DIAGNOSTICS.md                     # hermes-diag CLI reference
│   └── TOOLS.md                           # Utility scripts documentation
│
└── legacy/ (older docs, may be outdated)
    ├── SETUP.md                           # Original setup guide (Oct 2025)
    ├── CONFIGURATION.md                   # Original config guide (Oct 2025)
    └── DEVELOPMENT.md                     # Original dev guide (Oct 2025)
```

**Note:** The legacy docs (SETUP.md, CONFIGURATION.md, DEVELOPMENT.md) are from October 2025 and may not reflect recent features like YouTube collector, Platform Settings UI, Customer Management UI, parallel collection, etc. Refer to the current documentation above.

## Key Concepts

### Data Collection
- **Collectors** - Modules that fetch data from external sources
- **Parallel Collection** - Up to 4 customers collected concurrently
- **Rate Limiting** - Global coordination to prevent API abuse
- **Collection Intervals** - Per-source configurable timing (1-168 hours)

### AI Processing
- **Categorization** - Automatic classification (product update, financial, competitor, etc.)
- **Summarization** - Concise summaries via Claude
- **Sentiment Analysis** - Positive, negative, neutral, mixed
- **Priority Scoring** - Relevance ranking (0.0-1.0)
- **Entity Extraction** - Companies, technologies, people

### Smart Feed
- **Story Clustering** - Group similar items from multiple sources
- **Primary Items** - Most authoritative source displayed
- **Source Tiers** - Official > Primary > Secondary > Aggregator > Community
- **Smart/Full Modes** - Clustered view vs all items

## Common Tasks

### Add a New Customer
1. Click "Add Customer" in UI
2. Fill in basic info (name, domain, keywords)
3. Enable data sources
4. Configure source-specific settings (RSS feeds, LinkedIn profiles, etc.)
5. Save and trigger collection

### Configure YouTube Monitoring
1. Get YouTube API key from Google Cloud Console
2. Add `YOUTUBE_API_KEY` to `.env`
3. For each customer:
   - Enable YouTube in customer settings
   - Add channel IDs to monitor
   - Configure quality filters (optional)
4. See [YouTube Setup Guide](collectors/YOUTUBE.md)

### Troubleshoot Collection Errors
1. Check error banners in UI (top of feed)
2. Run diagnostics: `./hermes-diag all`
3. Review collection status: `./hermes-diag sources`
4. Check logs: `docker logs hermes-backend`
5. See [Diagnostics Guide](operations/DIAGNOSTICS.md)

### Migrate Database Schema
1. Check if migration is needed (error messages, new features)
2. Run appropriate migration script:
   ```bash
   docker exec -it hermes-backend python /app/tools/add_platform_settings.py
   ```
3. Restart backend: `docker compose restart backend`
4. See [Utility Tools](operations/TOOLS.md#database-migrations)

### Rebuild Vector Store
1. Run rebuild tool:
   ```bash
   docker exec -it hermes-backend python /app/tools/rebuild_vector_store.py
   ```
2. Wait for completion (shows progress)
3. Test search functionality
4. See [Vector Store Management](operations/TOOLS.md#vector-store-management)

## API Reference

Full API documentation available at `http://localhost:8000/docs` (OpenAPI/Swagger)

**Key Endpoints:**
- `GET /api/feed` - Intelligence items (paginated, filterable)
- `POST /api/search` - Semantic search
- `GET /api/customers` - List customers
- `POST /api/customers` - Create customer
- `PUT /api/customers/{id}` - Update customer
- `POST /api/jobs/trigger` - Manual collection
- `GET /api/analytics/daily-summary-ai/{customer_id}` - AI daily summary
- `GET /api/settings/platform` - Platform settings
- `PUT /api/settings/platform` - Update platform settings

## Configuration Reference

### Environment Variables
```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...          # Claude AI API key
NEWSAPI_KEY=...                        # NewsAPI.org key

# Optional
YOUTUBE_API_KEY=...                    # YouTube Data API v3
REDDIT_CLIENT_ID=...                   # Reddit API
REDDIT_CLIENT_SECRET=...
REDDIT_USER_AGENT=...
TWITTER_BEARER_TOKEN=...               # Twitter API
GITHUB_TOKEN=...                       # GitHub API (higher limits)
```

### Platform Settings (UI)
- **Daily Briefing** - Prompt templates, style, focus areas
- **AI Configuration** - Claude model, embedding model
- **Collection & Retention** - Schedules, intervals, retention period
- **Collector Settings** - Reddit filters, YouTube filters, Australian news sources

### Customer Configuration
- **Basic Info** - Name, domain, keywords, competitors
- **Data Sources** - Enable/disable per source
- **Source Config** - RSS feeds, LinkedIn profiles, YouTube channels, etc.
- **Display** - Tab color for visual organization

## Tech Stack

- **Backend:** FastAPI, SQLAlchemy, APScheduler
- **Database:** SQLite (relational), ChromaDB (vector store)
- **AI:** Anthropic Claude Sonnet 4.5, sentence-transformers
- **Frontend:** React 18, Vite
- **Data Sources:** 10+ APIs and web scraping (Playwright)
- **Deployment:** Docker, Docker Compose

## Support & Contributing

**Issues:**
- Check [diagnostics](operations/DIAGNOSTICS.md) first
- Review [architecture docs](architecture/COLLECTION_ARCHITECTURE.md)
- Check backend logs
- Review [roadmap](../ROADMAP.md) for known issues

**Contributing:**
- See [roadmap](../ROADMAP.md) for planned features
- Follow existing code patterns
- Add documentation for new features
- Test thoroughly before submitting

---

**Last Updated:** November 8, 2025
**Version:** Beta 1.0
**Status:** Production-ready for internal use
