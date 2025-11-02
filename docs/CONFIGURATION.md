# Hermes Configuration Guide

## Customer Configuration

Customers are configured in `config/customers.yaml`. Each customer represents a company or organization you want to monitor.

### Complete Configuration Example

```yaml
customers:
  - name: "Atlassian"
    domain: "atlassian.com"
    description: "Enterprise collaboration and productivity software company"

    # Search keywords
    keywords:
      - "Atlassian"
      - "Jira"
      - "Confluence"
      - "Trello"
      - "Bitbucket"

    # Competitors to monitor
    competitors:
      - "Microsoft Teams"
      - "Asana"
      - "Monday.com"
      - "Notion"

    # Stock market ticker
    stock_symbol: "TEAM"  # Use ".AX" suffix for ASX stocks (e.g., "CBA.AX")

    # RSS feeds from company
    rss_feeds:
      - url: "https://www.atlassian.com/blog/feed"
        name: "Atlassian Blog"

    # Social media
    twitter_handle: "@atlassian"
    linkedin_company_url: "https://www.linkedin.com/company/atlassian"
    github_org: "atlassian"

    # LinkedIn profiles to monitor
    linkedin_user_profiles:
      - profile_url: "https://www.linkedin.com/in/scott-farquhar-33156b1/"
        name: "Scott Farquhar"
        role: "Co-CEO & Co-Founder"
        notes: "Key executive, track major announcements"

    # Data collection configuration
    collection_config:
      # News sources
      news_enabled: true                    # NewsAPI (global news)
      australian_news_enabled: false        # AU-specific sources
      google_news_enabled: true             # Auto-generated Google News searches
      rss_enabled: true                     # RSS feeds above

      # Financial data
      stock_enabled: true                   # Yahoo Finance stock data

      # Social/Community
      reddit_enabled: true
      reddit_subreddits:
        - "atlassian"
        - "jira"

      hackernews_enabled: true              # Hacker News mentions
      twitter_enabled: false                # Requires Twitter API
      linkedin_enabled: true                # Company page
      linkedin_user_enabled: true           # Executive profiles

      # Developer
      github_enabled: true                  # Repository activity

      # Other
      pressrelease_enabled: false           # Press release services

      # Priority keywords for high-importance alerts
      priority_keywords:
        - "acquisition"
        - "CEO"
        - "earnings"
        - "layoffs"
        - "outage"
        - "security breach"
```

## Data Sources

### NewsAPI
**Enabled by:** `news_enabled: true`
**API Key:** `NEWS_API_KEY` in `.env`
**Coverage:** 80,000+ global news sources
**Rate Limit:** 100 requests/day (free tier)

Searches for customer name and keywords across major news outlets.

### Google News
**Enabled by:** `google_news_enabled: true`
**API Key:** None required
**Coverage:** Google News RSS feeds

Auto-generates RSS feeds for:
- Company name
- Top 3 competitors
- Combined keyword searches

### RSS Feeds
**Enabled by:** `rss_enabled: true`
**Configuration:** `rss_feeds` list in customer config

Monitor company blogs, newsrooms, and press release feeds. Add any valid RSS/Atom feed URL.

### Stock Market Data
**Enabled by:** `stock_enabled: true`
**API Key:** None (uses Yahoo Finance)
**Coverage:** Global stock exchanges

Collects:
- Daily price changes
- Volume data
- Market cap changes

**Stock Symbol Format:**
- US stocks: `AAPL`, `MSFT`, `TEAM`
- Australian stocks: `CBA.AX`, `TLS.AX`
- Other exchanges: Use Yahoo Finance format

### Australian News
**Enabled by:** `australian_news_enabled: true`
**API Key:** None
**Sources:**
- ITNews Australia
- ABC News
- Australian Financial Review

Targeted for Australian companies and tech industry.

### LinkedIn
**Enabled by:** `linkedin_enabled: true` (company), `linkedin_user_enabled: true` (profiles)
**API Key:** None (uses Playwright scraping)
**Setup Required:** Yes (see SETUP.md)

Monitors:
- **Company Page:** Company updates and posts
- **User Profiles:** Executive activity and posts

**Note:** Requires Playwright setup and LinkedIn credentials. May violate LinkedIn ToS.

### Reddit
**Enabled by:** `reddit_enabled: true`
**API Key:** `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` in `.env`
**Configuration:** `reddit_subreddits` list

Monitors specified subreddit communities for company mentions and discussions.

### Hacker News
**Enabled by:** `hackernews_enabled: true`
**API Key:** None
**Coverage:** HN front page and search

Monitors Hacker News for company/product mentions in stories and comments.

### GitHub
**Enabled by:** `github_enabled: true`
**API Key:** `GITHUB_TOKEN` in `.env` (optional, but recommended for higher rate limits)
**Configuration:** `github_org` in customer config

Monitors:
- Repository releases
- Major commits
- Issue discussions
- Pull requests

### Twitter/X
**Enabled by:** `twitter_enabled: true`
**API Key:** `TWITTER_BEARER_TOKEN` in `.env`
**Configuration:** `twitter_handle` in customer config

Monitors company Twitter account for tweets and engagement.

**Note:** Twitter API access has become restricted. May require paid tier.

## Priority Keywords

Priority keywords trigger higher priority scores for matching articles.

**Common Priority Keywords:**
- `acquisition`, `merger`
- `CEO`, `CFO`, `CTO` (executive changes)
- `earnings`, `revenue`, `profit`
- `layoffs`, `restructuring`
- `outage`, `downtime`, `incident`
- `security breach`, `data leak`
- `lawsuit`, `litigation`
- `IPO`, `funding round`

## Collection Schedule

Configured in `backend/app/config/settings.py`:

```python
# Scheduler settings
enable_scheduler: bool = True
hourly_collection_enabled: bool = True
daily_collection_enabled: bool = True
daily_collection_hour: int = 10  # 10 AM UTC
```

### Default Schedule
- **Hourly:** NewsAPI, Google News, RSS feeds (quick updates)
- **Daily @ 10 AM UTC:** All sources comprehensive scan
- **On-Demand:** Manual trigger via dashboard or API

## Data Retention

Configured via `INTELLIGENCE_RETENTION_DAYS` environment variable (default: 90 days).

Purge old data:
```bash
# Manual purge (keep last 30 days)
curl -X POST http://localhost:8000/api/jobs/purge?retention_days=30
```

## Advanced Configuration

### AI Processing

Edit `backend/app/config/settings.py`:

```python
ai_model: str = "claude-sonnet-4-5-20250929"
max_tokens_summary: int = 800
```

### Rate Limiting

```python
news_api_rate_limit: int = 100      # NewsAPI calls per day
claude_api_rate_limit: int = 50     # Claude API calls per minute
```

### CORS Origins

For frontend hosted on different domain:

```python
cors_origins: str = "http://localhost:3000,https://yourdomain.com"
```

## Using the Configuration Wizard

The easiest way to add customers is via the dashboard:

1. Navigate to http://localhost:3000
2. Click **"+ Add Customer"**
3. Enter company name
4. AI will research and populate all fields
5. Review and edit:
   - ✅ Verify executive information is current
   - ✅ Add/remove competitors
   - ✅ Adjust keywords
   - ✅ Enable/disable data sources
6. Generate YAML configuration
7. Paste into `config/customers.yaml`
8. Restart backend

The wizard provides:
- Current company information
- Web-scraped executive data
- AI-suggested competitors
- Auto-generated keywords
- Data source recommendations

## Troubleshooting

### Collection Not Finding Articles
- Check keywords are spelled correctly
- Add more keyword variations
- Enable more data sources
- Check API keys are valid
- Review logs: `docker logs atl-intel-backend-1`

### Too Much Noise/Irrelevant Articles
- Reduce keyword count
- Add more specific priority_keywords
- Use customer wizard to get AI-suggested keywords
- Disable noisy sources

### Missing Stock Data
- Verify stock symbol format (use Yahoo Finance format)
- Check if company is publicly traded
- Australian stocks need `.AX` suffix

## Best Practices

1. **Start Small** - Monitor 2-3 customers initially
2. **Use Wizard** - Let AI research company info
3. **Verify Executives** - Executive data may be outdated
4. **Quality Keywords** - 10-15 focused keywords better than 50 generic ones
5. **Enable Relevant Sources** - Don't enable every source for every customer
6. **Monitor Priority Keywords** - Keep to 5-8 high-impact terms
7. **Review Daily Summaries** - Use AI summaries to stay informed quickly
8. **Backup Regularly** - Backup database before major changes
