# Hermes Setup Guide

Complete setup instructions for deploying Hermes.

## Prerequisites

- **Docker & Docker Compose** (or Podman with podman-compose)
- **API Keys:**
  - [Anthropic Claude API](https://console.anthropic.com/) - Required for AI processing
  - [NewsAPI](https://newsapi.org/) - Free tier available (100 requests/day)

## Quick Start (5 Minutes)

### 1. Clone and Configure

```bash
# Clone the repository
git clone <repository-url>
cd atl-intel

# Copy environment template
cp .env.example .env
```

### 2. Add API Keys

Edit `.env` and add your credentials:

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-xxxxx
NEWS_API_KEY=xxxxx

# Optional (for additional data sources)
REDDIT_CLIENT_ID=xxxxx
REDDIT_CLIENT_SECRET=xxxxx
TWITTER_BEARER_TOKEN=xxxxx
GITHUB_TOKEN=xxxxx
```

### 3. Start the Platform

```bash
# Using Docker Compose
docker-compose up -d

# Or using Podman
podman-compose up -d
```

### 4. Access Hermes

- **Dashboard:** http://localhost:3000
- **API Docs:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/api/health

## Adding Your First Customer

### Option 1: Use the Configuration Wizard (Recommended)

1. Open the dashboard at http://localhost:3000
2. Click **"+ Add Customer"** in the customer tabs
3. Enter the company name (e.g., "Atlassian")
4. The AI will automatically research:
   - Company information
   - Executive team
   - Competitors
   - Monitoring keywords
5. Review and edit the results
6. Click **"Generate Configuration"**
7. Copy the YAML to `config/customers.yaml`
8. Restart the backend: `docker-compose restart backend`

### Option 2: Manual Configuration

Edit `config/customers.yaml`:

```yaml
customers:
  - name: "Atlassian"
    domain: "atlassian.com"
    description: "Enterprise collaboration and productivity software"

    keywords:
      - "Atlassian"
      - "Jira"
      - "Confluence"
      - "Trello"

    competitors:
      - "Microsoft"
      - "Asana"
      - "Monday.com"

    stock_symbol: "TEAM"

    collection_config:
      news_enabled: true
      stock_enabled: true
      rss_enabled: true
      australian_news_enabled: false
      google_news_enabled: true
      reddit_enabled: true
      reddit_subreddits:
        - "atlassian"
        - "jira"

      priority_keywords:
        - "acquisition"
        - "CEO"
        - "earnings"
        - "outage"
```

Restart the backend to load the new configuration:
```bash
docker-compose restart backend
```

## Trigger Your First Collection

### Via Dashboard
1. Click **"Trigger Collection"** button in the header
2. Wait 2-5 minutes for data to appear
3. Refresh the page

### Via API
```bash
curl -X POST http://localhost:8000/api/jobs/trigger
```

### Via Command Line
```bash
docker exec -it atl-intel-backend-1 python -c "
from app.scheduler.collection import run_collection
import asyncio
asyncio.run(run_collection())
"
```

## Configuration Reference

### Environment Variables

#### Required
- `ANTHROPIC_API_KEY` - Claude API key for AI processing
- `NEWS_API_KEY` - NewsAPI key for global news

#### Optional Data Sources
- `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` - Reddit API access
- `TWITTER_BEARER_TOKEN` - Twitter/X API access
- `GITHUB_TOKEN` - GitHub API access (higher rate limits)

#### Application Settings
- `APP_ENV` - `development` or `production` (default: development)
- `LOG_LEVEL` - `DEBUG`, `INFO`, `WARNING`, `ERROR` (default: INFO)
- `API_PORT` - Backend port (default: 8000)
- `ENABLE_SCHEDULER` - Enable automated collections (default: true)
- `INTELLIGENCE_RETENTION_DAYS` - Data retention period (default: 90)

#### AI Settings
- `AI_MODEL` - Claude model to use (default: claude-sonnet-4-5-20250929)
- `MAX_TOKENS_SUMMARY` - Max tokens for summaries (default: 800)

### Customer Configuration

See `config/customers.yaml` for the full schema. Key fields:

- **name** - Company name (required)
- **domain** - Company website domain
- **keywords** - Terms to search for
- **competitors** - Competitor companies to monitor
- **stock_symbol** - Stock ticker (e.g., "TEAM", "CBA.AX")
- **rss_feeds** - Company blog/newsroom RSS feeds
- **linkedin_company_url** - LinkedIn company page
- **twitter_handle** - Twitter/X handle
- **collection_config** - Enable/disable specific data sources

## LinkedIn Setup (Optional)

LinkedIn scraping requires Playwright browser automation:

### 1. Install Playwright in Container

```bash
docker exec -it atl-intel-backend-1 bash
playwright install chromium
playwright install-deps chromium
exit
```

### 2. Add LinkedIn Credentials

Edit `.env`:
```bash
LINKEDIN_EMAIL=your_email@example.com
LINKEDIN_PASSWORD=your_password
LINKEDIN_HEADLESS=true
```

### 3. Enable LinkedIn Collection

In `config/customers.yaml`:
```yaml
collection_config:
  linkedin_enabled: true
  linkedin_user_enabled: true
  linkedin_user_profiles:
    - profile_url: "https://linkedin.com/in/executive-name"
      name: "John Doe"
      role: "CEO"
```

**Note:** LinkedIn scraping may be fragile and against LinkedIn's ToS. Use at your own risk.

## Database Migrations

After upgrading Hermes, run migrations:

```bash
docker exec -it atl-intel-backend-1 python /app/tools/migrate_ai_processing_fields.py
```

## Troubleshooting

### No Data Appearing
1. Check logs: `docker logs atl-intel-backend-1`
2. Verify API keys are correct in `.env`
3. Trigger manual collection
4. Check job status: `GET /api/jobs`

### AI Processing Failures
- Check Anthropic API quota/credits
- Look for items with ⚠️ badge in UI
- Manually reprocess: `POST /api/jobs/reprocess-failed`

### Vector Search Not Working
```bash
docker exec -it atl-intel-backend-1 python /app/tools/rebuild_vector_store.py
```

### Container Won't Start
```bash
# View logs
docker logs atl-intel-backend-1

# Rebuild containers
docker-compose down
docker-compose up -d --build
```

## Data Backup

### Backup Database
```bash
cp data/db/intelligence.db data/db/intelligence.db.backup
```

### Backup Vector Store
```bash
cp -r data/chroma data/chroma.backup
```

## Next Steps

1. **Configure Customers** - Add companies you want to monitor
2. **Set Collection Schedule** - Adjust in `app/config/settings.py` if needed
3. **Explore the Dashboard** - Try filtering, search, and daily summaries
4. **Review Utility Tools** - See `backend/tools/README.md`
5. **Customize** - Adjust AI prompts, add data sources, modify UI

For development, see [DEVELOPMENT.md](DEVELOPMENT.md).
