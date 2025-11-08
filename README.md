# Hermes

> *Automated customer intelligence platform for technical sales teams*

An AI-powered platform that aggregates and analyzes information from 10+ sources to help technical sales leads stay informed about their customers and competitors.

## ✨ Key Features

### 📊 Multi-Source Intelligence Gathering
- **NewsAPI** - 80,000+ global news sources
- **Google News** - Auto-generated company & competitor searches
- **RSS Feeds** - Company blogs, newsrooms, press releases
- **Stock Market** - Yahoo Finance (with ASX support)
- **Australian News** - ABC News, Guardian AU, SMH, and more
- **LinkedIn** - Executive profiles and company updates
- **Reddit** - Community discussions and insights
- **YouTube** - Video content via transcripts with quality filters
- **Twitter/X** - Social media monitoring
- **GitHub** - Repository activity and releases
- **Web Scraper** - Custom sources with CSS selectors

### 🤖 AI-Powered Processing (Claude Sonnet 4.5)
- **Smart Summarization** - Concise, actionable summaries
- **Automatic Categorization** - Product updates, financial news, competitor moves, etc.
- **Sentiment Analysis** - Positive, negative, neutral, mixed
- **Priority Scoring** - Intelligent ranking of relevance
- **Entity Extraction** - Companies, technologies, people
- **Advanced Filtering** - Removes ads, deals, and promotional content
- **Daily Executive Summaries** - AI-generated briefings

### 🔍 Intelligent Search & Discovery
- **Semantic Search** - ChromaDB vector store with sentence transformers
- **Natural Language Queries** - Find related content intelligently
- **Customer-Specific Filtering** - Scoped to relevant organizations

### 🎯 Customer Configuration Wizard
- **AI-Powered Research** - Automatically discover company information
- **Leadership Discovery** - Find executives via web scraping
- **Competitor Analysis** - Identify key competitors
- **Keyword Generation** - Smart monitoring terms
- **One-Click YAML Export** - Ready-to-use configuration

### ⚡ Reliability & Error Handling
- **Automatic Retry** - 3 attempts with exponential backoff
- **Failed Item Tracking** - Visual indicators for items needing reprocessing
- **Manual Reprocessing** - API endpoint to retry failed AI processing
- **Job Status Monitoring** - Track collection success/failures

### 📅 Automated Workflows
- **Hourly Collections** - Frequent news updates
- **Daily Comprehensive Scans** - All sources, all customers
- **Manual Triggers** - On-demand collection
- **Data Retention** - Configurable purge policies (default: 90 days)

## Architecture

- **Backend**: Python FastAPI
- **Database**: SQLite (relational data)
- **Vector Store**: ChromaDB (semantic search)
- **AI**: Anthropic Claude API for summarization and analysis
- **Frontend**: React with Vite
- **Deployment**: Docker containers

## Quick Start

### Prerequisites

- Docker and Docker Compose
- API Keys:
  - Anthropic Claude API key
  - NewsAPI key (free tier available at https://newsapi.org)

### Setup

1. Clone the repository
2. Copy `.env.example` to `.env` and fill in your API keys:
   ```bash
   cp .env.example .env
   ```

3. Configure your customers in `config/customers.yaml`

4. Start the application:
   ```bash
   docker-compose up -d
   ```

5. Access the dashboard at `http://localhost:3000`
6. API documentation at `http://localhost:8000/docs`

## Configuration

Edit `config/customers.yaml` to add customers you want to monitor:

```yaml
customers:
  - name: "Example Corp"
    domain: "example.com"
    keywords:
      - "example corp"
      - "example inc"
    competitors:
      - "Competitor A"
      - "Competitor B"
    stock_symbol: "EXMP"
    rss_feeds:
      - "https://example.com/blog/feed"
```

## Data Collection Schedule

- **Hourly**: News API updates
- **Daily**: Comprehensive scan of all sources
- **On-demand**: Manual trigger via API or dashboard

## Development

### Backend Development

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend Development

```bash
cd frontend
npm install
npm run dev
```

## 📚 Documentation

### Getting Started
- **Quick Start** - See installation instructions above
- **[Roadmap](ROADMAP.md)** - Development roadmap and completed features

### Operations & Maintenance
- **[Diagnostics CLI](docs/operations/DIAGNOSTICS.md)** - hermes-diag tool reference
- **[Utility Tools](docs/operations/TOOLS.md)** - Database migrations and maintenance scripts

### Data Sources
- **[Collector Overview](docs/collectors/README.md)** - All available data sources and configuration
- **[YouTube Setup](docs/collectors/YOUTUBE.md)** - YouTube API setup and channel monitoring

### Architecture
- **[Collection Architecture](docs/architecture/COLLECTION_ARCHITECTURE.md)** - Parallel collection, rate limiting, and scraping strategies

## 🚀 API Reference

Full API documentation available at `http://localhost:8000/docs` (OpenAPI/Swagger)

**Key Endpoints:**
- `GET /api/feed` - Intelligence items (paginated, filterable)
- `POST /api/search` - Semantic search
- `GET /api/customers` - List customers
- `POST /api/jobs/trigger` - Manual collection
- `GET /api/analytics/daily-summary-ai/{customer_id}` - AI daily summary
- `POST /api/jobs/reprocess-failed` - Retry failed AI processing

## 🛠️ Tech Stack

- **Backend:** FastAPI, SQLAlchemy, APScheduler
- **AI:** Anthropic Claude (Sonnet 4.5), sentence-transformers
- **Vector DB:** ChromaDB
- **Frontend:** React 18, Vite, date-fns
- **Data Sources:** NewsAPI, Yahoo Finance, RSS, LinkedIn (Playwright)
- **Deployment:** Docker, Docker Compose

## 📈 Project Status

**Current Version:** Beta
**Status:** Production-ready for internal use

### Known Limitations
- LinkedIn scraping may be fragile (Playwright-based)
- NewsAPI free tier: 100 requests/day limit
- Single-user system (no authentication)
- No mobile app (responsive web only)

## 🤝 Contributing

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for development setup and guidelines.

## 📄 License

MIT License - See LICENSE file for details

---

**Hermes** - *Delivering intelligence at the speed of thought* ⚡
