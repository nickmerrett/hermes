# Data Source Collectors

Hermes collects intelligence from 10+ data sources. Each collector is configured per-customer and runs on configurable intervals.

## Available Collectors

### News & Media

#### NewsAPI
- **What:** 80,000+ global news sources
- **API:** NewsAPI.org (free tier: 100 requests/day)
- **Interval:** 1 hour (default)
- **Configuration:** Requires `NEWSAPI_KEY` environment variable
- **Per-customer:** Enable via `news_enabled: true`

#### Google News
- **What:** Automated Google News searches for customer keywords
- **API:** Web scraping (no API key required)
- **Interval:** 6 hours (default)
- **Configuration:** Auto-enabled for all customers
- **Per-customer:** Uses customer keywords automatically

#### Australian News
- **What:** 6 Australian news sources (ABC, Guardian AU, SMH, etc.)
- **API:** RSS feeds
- **Interval:** 6 hours (default)
- **Configuration:** Platform Settings → Collector Settings → Australian News
- **Per-customer:** Enable via `australian_news_enabled: true`

#### Press Releases
- **What:** Official company press releases
- **API:** RSS feeds from company newsrooms
- **Interval:** 12 hours (default)
- **Configuration:** Add RSS feed URLs to customer config
- **Per-customer:** `rss_feeds` list with feed URLs

---

### Social Media & Community

#### Reddit
- **What:** Community discussions and sentiment
- **API:** Async PRAW (Reddit API)
- **Interval:** 24 hours (default)
- **Configuration:** Requires Reddit API credentials
- **Setup:** See [Reddit Setup Guide](REDDIT.md)
- **Features:**
  - Engagement filtering (min upvotes/comments)
  - AI thread summarization for large discussions
  - Subreddit monitoring

#### LinkedIn (Playwright)
- **What:** Executive profiles and company updates
- **API:** Web scraping via Playwright (browser automation)
- **Interval:** 24 hours (default)
- **Configuration:** See [LinkedIn Setup Guide](LINKEDIN.md)
- **Features:**
  - "Low and slow" scraping strategy
  - Configurable delays (conservative/moderate/aggressive)
  - Session persistence
  - Profile post monitoring

#### Twitter/X
- **What:** Social media monitoring
- **API:** Twitter API (requires credentials)
- **Interval:** 3 hours (default)
- **Configuration:** Requires Twitter API keys
- **Per-customer:** Enable via `twitter_enabled: true`

---

### Development & Technology

#### GitHub
- **What:** Repository activity and releases
- **API:** GitHub REST API
- **Interval:** 12 hours (default)
- **Configuration:** Optional GitHub token for higher rate limits
- **Per-customer:** Specify repos in `github_repos` and `github_orgs`

#### YouTube
- **What:** Video content via transcripts
- **API:** YouTube Data API v3
- **Interval:** 12 hours (default)
- **Configuration:** See [YouTube Setup Guide](YOUTUBE.md)
- **Features:**
  - Channel monitoring by channel ID
  - Keyword-based video search
  - Automatic transcript fetching
  - Quality filters (min views, min channel subscribers)
  - Enable/disable keyword search toggle

---

### Financial

#### Yahoo Finance (Stock & News)
- **What:** Stock prices and financial news
- **API:** `yfinance` Python library
- **Interval:** 1 hour for news, 24 hours for prices (default)
- **Configuration:** No API key required
- **Per-customer:** Enable via `stock_enabled: true`, set `stock_symbol`
- **Features:**
  - 24-hour caching to avoid rate limits
  - Exponential backoff retry logic
  - Supports all Yahoo Finance exchanges (including ASX)

---

### Custom Sources

#### Web Scraper
- **What:** Custom website monitoring with CSS selectors
- **API:** Web scraping via requests/BeautifulSoup
- **Interval:** 12 hours (default)
- **Configuration:** Per-customer `web_scraping_sources`
- **Format:**
  ```yaml
  web_scraping_sources:
    - url: "https://example.com/news"
      title_selector: "h2.article-title"
      link_selector: "a.article-link"
      date_selector: "time.published"
  ```

#### RSS Feeds
- **What:** Generic RSS/Atom feed monitoring
- **API:** RSS parsing via `feedparser`
- **Interval:** 1 hour (default)
- **Configuration:** Add feed URLs to customer config
- **Per-customer:** `rss_feeds` list
- **Features:**
  - Trusted source flagging (prevents false "irrelevant" marking)
  - Supports RSS 2.0, Atom, and RSS 1.0

---

## Collector Configuration

### Global Configuration (Platform Settings)

**Collection Timing:**
- Per-source intervals (1-168 hours)
- Collection days (Mon-Sun selection)
- Hourly vs daily collection toggle

**Collector-Specific Settings:**

**Reddit:**
- Minimum upvotes threshold
- Minimum comments threshold
- AI summarization threshold
- Posts per subreddit limit
- Lookback days

**YouTube:**
- Enable keyword search toggle
- Minimum views filter
- Minimum channel subscribers filter

**Australian News:**
- Manage news sources (add/remove/edit)
- Per-source enable/disable
- RSS feed URLs

### Per-Customer Configuration

Enable/disable collectors in Customer Edit modal:

```yaml
collection_config:
  news_enabled: true
  reddit_enabled: true
  linkedin_enabled: false
  stock_enabled: true
  twitter_enabled: false
  github_enabled: false
  hackernews_enabled: false  # Deprecated
  web_scraping_enabled: true
  australian_news_enabled: true
  youtube_enabled: true
```

**Source-specific config:**
```yaml
# Reddit
reddit_subreddits: ["technology", "programming"]

# LinkedIn
linkedin_user_profiles:
  - url: "https://linkedin.com/in/john-doe"
    description: "CEO"

# GitHub
github_repos: ["owner/repo"]
github_orgs: ["organization"]

# YouTube
youtube_channels:
  - channel_id: "UCxxxxxx"
    name: "Company Official Channel"

# RSS Feeds (trusted sources)
rss_feeds:
  - url: "https://example.com/feed"
    is_trusted_source: true  # Prevents false "irrelevant" categorization

# Web Scraping
web_scraping_sources:
  - url: "https://example.com/news"
    title_selector: "h2.title"
    link_selector: "a.link"
    date_selector: "time"
```

## Collector Architecture

All collectors inherit from `RateLimitedCollector` base class:

**File:** `backend/app/collectors/base.py`

**Features:**
- Built-in rate limiting
- Automatic retry logic
- Error handling
- Collection status tracking
- Incremental processing support

**Rate Limiting:**
- Per-collector local rate limiting
- Global rate limiter coordination (for parallel collections)
- Configurable delays for scraping

## Collection Flow

1. **Trigger:** APScheduler job or manual trigger
2. **Source Selection:** Check which sources are due for collection
3. **Parallel Execution:** Up to 4 customers collected concurrently
4. **Collection:** Each collector gathers raw items
5. **AI Processing:** Claude analyzes and categorizes items
6. **Storage:** Items saved to database and vector store
7. **Status Update:** Collection status tracked per source/customer
8. **UI Update:** Items appear incrementally in feed

## Adding New Collectors

To add a new data source:

1. **Create collector class** in `backend/app/collectors/`
   - Inherit from `RateLimitedCollector`
   - Implement `collect()` method
   - Return list of `IntelligenceItemCreate` objects

2. **Add to collector registry** in `backend/app/scheduler/collection.py`

3. **Add configuration options**
   - Platform settings (if global)
   - Customer config schema (if per-customer)

4. **Update UI**
   - Add toggle in Customer Edit modal
   - Add settings in Platform Settings modal (if needed)

5. **Write documentation**
   - Setup guide in `docs/collectors/`
   - Update this README

## Collector Status Monitoring

**API Endpoint:**
```
GET /api/feed/collection-errors
```

Returns active collection errors for UI display.

**Collection Status Table:**
Tracks per-customer, per-source collection health:
- Last run time
- Last success time
- Error count and message
- Status (success/error/auth_required)

**Error Banners:**
- Yellow banner for authentication issues
- Red banner for collection errors
- Dismissible with persistent state

## Rate Limiting Strategy

See [Collection Architecture](../architecture/COLLECTION_ARCHITECTURE.md) for details on:
- Global rate limiter
- Per-source rate limits
- LinkedIn scraping strategies
- Anti-detection measures

## Troubleshooting

### Collector Not Running

1. Check if enabled in customer config
2. Check collection interval hasn't been met
3. Review collection status in database
4. Check error banners in UI
5. Review backend logs

### Authentication Errors

**LinkedIn:**
- Check if logged in (session persists in `data/auth/`)
- Look for "authwall" errors in logs
- May need to log in again via Playwright

**Reddit:**
- Verify Reddit API credentials in `.env`
- Check Reddit account hasn't been banned
- Verify OAuth credentials are valid

**Twitter:**
- Verify Twitter API keys in `.env`
- Check API access level (free/basic/pro)
- Verify account hasn't been suspended

### Rate Limiting

- Check rate limiter statistics in logs
- Adjust collection intervals if hitting limits
- For LinkedIn, switch to more conservative strategy
- Consider rotating API keys (if applicable)

## Setup Guides

Detailed setup instructions for specific collectors:

- **[YouTube Setup](YOUTUBE.md)** - YouTube Data API, channel IDs, transcript configuration
- **[LinkedIn Setup](LINKEDIN.md)** - Playwright authentication, scraping strategies (coming soon)
- **[Reddit Setup](REDDIT.md)** - API credentials, subreddit configuration (coming soon)

## Deprecated Collectors

### HackerNews
- **Status:** Removed November 2025
- **Reason:** Low signal-to-noise ratio, limited relevance for B2B intelligence
- **Alternative:** Use Reddit r/programming or r/technology instead

### GitHub
- **Status:** Removed November 2025
- **Reason:** Limited applicability for customer intelligence (more for competitor/vendor monitoring)
- **Alternative:** Can be re-added if specific use case arises

---

**Last Updated:** November 8, 2025
**Active Collectors:** 11
**Supported APIs:** NewsAPI, Reddit, YouTube, Yahoo Finance, Twitter, GitHub, LinkedIn (scraping)
