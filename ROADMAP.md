# Hermes Development Roadmap

## Current Status: Beta Release

Hermes is production-ready for internal use with core features fully functional.

## Post-Beta Enhancement Roadmap

### Priority 0: Critical Improvements

#### 28. Add Source Citations to Daily Executive Summary
**Status:** Pending
**Effort:** Medium
**Description:** Include references and citations in daily executive summaries so users can verify claims and explore source material.

**Current Problem:**
- Daily summaries make claims without attribution
- Users can't verify information or find original sources
- No way to trace summary statements back to specific articles
- Reduces trust and credibility of AI-generated summaries

**Proposed Solution - Inline Citations:**
```markdown
The company announced Q3 earnings beat analyst expectations [1], with revenue
up 15% year-over-year [2]. Management cited strong demand in the Asia-Pacific
region [1] and successful product launches [3].

---
Sources:
[1] Company Q3 Earnings Report - Press Release - Oct 15, 2025
    https://company.com/investors/q3-2025
[2] Q3 Revenue Growth Exceeds Forecasts - Reuters - Oct 15, 2025
    https://reuters.com/article/...
[3] New Product Line Drives Growth - TechCrunch - Oct 12, 2025
    https://techcrunch.com/2025/10/12/...
```

**Implementation Phases:**

**Phase 1: Enhanced AI Prompt (2-3 days)**
- Update daily summary AI prompt to include citation tracking
- Instruct Claude to reference source articles using [1], [2], [3] format
- Generate bibliography with article titles, sources, dates, URLs
- Test with various customer data sets

**Phase 2: Structured Citation Data (1 week)**
- Add `citations` field to DailySummary model (JSON array)
- Structure: `{ref_id, item_id, title, source, date, url, excerpt}`
- Store mapping between summary claims and source articles
- Backend: Link citations back to IntelligenceItem records

**Phase 3: Enhanced UI Display (1 week)**
- **Inline Citations**: Clickable [1], [2], [3] references in summary text
- **Sources Section**: Collapsible bibliography at bottom of summary
- **Hover Preview**: Tooltip shows article title and excerpt on citation hover
- **Click Action**: Opens article detail modal or navigates to source URL
- **Visual Indicators**: Icons for source types (press release, news, social, etc.)

**Phase 4: Source Quality Indicators (3-4 days)**
- **Tier Badges**: Display source tier (official/primary/secondary/aggregator/social)
- **Authority Indicators**: Highlight authoritative sources (Reuters, Bloomberg, company newsroom)
- **Freshness**: Show how recent the source is ("2 hours ago")
- **Multiple Sources**: Badge showing "Confirmed by 3 sources" when multiple articles report same fact

**Benefits:**
- ✅ Increased trust and credibility
- ✅ Verifiable claims with source material
- ✅ Better understanding of where information comes from
- ✅ Easier fact-checking and validation
- ✅ Transparency in AI-generated content
- ✅ Compliance with AI content guidelines (attribution)

**Future Enhancements:**
- Citation analytics - Track which sources are cited most frequently
- Source quality scoring - Weight citations by source authority
- Multi-source verification - Highlight facts confirmed by multiple sources
- Disputed claims - Flag when sources disagree
- Citation export - Export bibliography in academic formats (BibTeX, APA)
- Interactive timeline - Show how story developed across sources over time

---

### Priority 1: Data Source Improvements

#### 1. Fix Stock Market Data Collection
**Status:** ✅ Complete
**Effort:** Small
**Description:** Ensure Yahoo Finance integration works reliably for all stock symbols, especially ASX stocks.

**Completed Improvements:**
- ✅ Added 24-hour caching to avoid Yahoo Finance rate limits
- ✅ Implemented exponential backoff retry logic (5 attempts: 3s, 6s, 12s, 24s)
- ✅ Graceful error handling - collection continues even if stock API fails
- ✅ Separate caching for news, price history, and stock info
- ✅ Cache stored in `data/cache/stock/` directory

**Technical Details:**
- Cache duration: 24 hours (suitable for non-real-time needs)
- Max retries: 5 with exponential backoff
- Fallback behavior: Uses cached data when API fails
- Works with all international exchanges supported by Yahoo Finance (including ASX)

---

#### 2. Implement Hybrid Search for Names and Keywords
**Status:** ✅ Complete
**Effort:** Small
**Description:** Improve semantic search to handle exact name matches and specific terms by combining keyword matching with vector similarity search.

**Problem Solved:**
- Pure semantic search was poor at finding people's names (e.g., searching "Nuno" didn't find "Nuno Matos")
- Embeddings don't understand that partial names should match full names in documents
- Users expect exact keyword matches for names, companies, specific terms

**Implementation:**
- **Keyword/Text Search:** SQL LIKE search in title and content for exact matches
  - Score: 1.0 for title matches, 0.9 for content matches
- **Semantic/Vector Search:** ChromaDB vector similarity for concepts and topics
  - Score: 0.0-1.0 based on embedding similarity
- **Merged Ranking:** Combines both methods, boosting items found by both

**Results:**
- Search for "Nuno" now returns 5 perfect matches (1.00 similarity)
- Search for "Telstra" returns exact keyword matches
- Concept searches still work via semantic matching
- No reindexing required - works in real-time

**Technical Details:**
- Modified `/api/search` endpoint in `backend/app/api/search.py`
- Searches both methods in parallel
- Merges results with intelligent scoring
- Backward compatible - no frontend changes needed

---

#### 3. Add AFR (Australian Financial Review) as News Source
**Status:** Pending
**Effort:** Medium
**Description:** Integrate Australian Financial Review for high-quality Australian business and technology news.

**Tasks:**
- Investigate AFR RSS feeds or API access
- Implement AFR collector
- Add AFR-specific content parsing
- Test with Australian customers

---

#### 4. Improve Google News Results Quality
**Status:** Pending
**Effort:** Medium
**Description:** Enhance Google News collector to return more relevant, higher-quality results.

**Tasks:**
- Refine search query generation
- Improve result filtering (remove duplicates, low-quality sources)
- Add source ranking/weighting
- Handle CAPTCHA/rate limiting better
- Consider using Google News API if available

---

#### 5. Explore and Add Other High-Quality News Sources
**Status:** Pending
**Effort:** Large
**Description:** Research and integrate additional premium news sources for comprehensive coverage.

**Potential Sources:**
- **Bloomberg** - Financial and business news
- **Reuters** - Global news agency
- **TechCrunch** - Technology industry news
- **The Information** - Tech industry analysis (paid)
- **Financial Times** - Global business news
- **Wall Street Journal** - Business and finance
- **Industry-specific sources** - Vertical-specific publications

**Tasks:**
- Research API access and pricing
- Evaluate RSS feed availability
- Assess content quality vs. cost
- Implement collectors for selected sources
- Add source attribution and links

---

#### 6. Add YouTube Channel Monitoring (Transcript-Based)
**Status:** ✅ Complete
**Effort:** Small-Medium
**Description:** Monitor YouTube videos via transcripts for company announcements, executive interviews, product launches, and industry commentary.

**Use Cases:**
- **Company channels** - Official announcements, product demos, earnings calls
- **Executive interviews** - CEO/founder appearances on podcasts and shows
- **Industry channels** - Analyst coverage, competitor reviews, market commentary
- **Conference talks** - Speaking engagements, keynotes, panel discussions

**Implementation:**
- Use YouTube Data API v3 for video metadata
- Fetch transcripts using YouTube Transcript API (unofficial Python library)
- Process transcripts as text intelligence (same as news articles)
- Extract key quotes and themes via AI
- Link to video with URL
- Skip videos without available transcripts

**Technical Details:**
- **API:** YouTube Data API v3 (10,000 units/day free quota)
- **Authentication:** API key (simple)
- **Transcripts:** youtube-transcript-api Python library
  - Supports auto-generated and manual captions
  - Works for most English videos
  - Free, no additional API needed
- **Processing:** Treat transcript as `content`, video title as `title`
- **Rate Limiting:** API quota based, track usage
- **Source tier:** 3 (secondary - video content)

**Advantages of Transcript Approach:**
- ✅ No speech-to-text costs or complexity
- ✅ Fast processing (text-based)
- ✅ Uses existing AI processing pipeline
- ✅ Searchable content
- ✅ Extract exact quotes
- ✅ Small data footprint

**Limitations:**
- Only works for videos with transcripts (most major channels have them)
- Auto-generated transcripts may have errors
- Skip videos without transcripts

**Configuration (per customer):**
```yaml
youtube_channels:
  - channel_id: "UCxxxxxx"
    name: "Company Official Channel"
  - channel_id: "UCyyyyyy"
    name: "Industry News Channel"
youtube_keywords:
  - "company name CEO"
  - "company name product launch"
transcript_language: "en"  # Default to English
```

**Collection Flow:**
1. Search YouTube for keywords or monitor specific channels
2. Get video metadata (title, description, date, views)
3. Check if transcript is available
4. If yes: Fetch transcript, create intelligence item with full text
5. If no: Skip or create item with description only
6. AI processes transcript like any other content
7. Display in feed with video thumbnail and link

**Implemented Features:**
- ✅ YouTube Data API v3 integration
- ✅ `youtube-transcript-api` for fetching transcripts
- ✅ Channel monitoring by channel ID
- ✅ Keyword-based video search
- ✅ Automatic transcript fetching (auto-generated + manual)
- ✅ Video metadata tracking (views, likes, comments, duration)
- ✅ Configurable collection intervals (default: 12 hours)
- ✅ Language preference (default: English)
- ✅ Rate limiting and quota management
- ✅ Full customer configuration support
- ✅ Setup documentation (YOUTUBE_SETUP.md)

**Technical Implementation:**
- Backend: `app/collectors/youtube_collector.py`
- Settings: `YOUTUBE_API_KEY` environment variable
- Configuration: Per-customer `youtube_enabled`, `youtube_channels`, `youtube_keywords`
- Default interval: 12 hours
- Quota: 10,000 units/day (YouTube API free tier)

---

#### 7. Add Podcast Episode Monitoring (Transcript-Based)
**Status:** Pending
**Effort:** Small-Medium
**Description:** Track podcast episodes via transcripts for executive appearances, industry commentary, and company mentions.

**Use Cases:**
- **Executive appearances** - CEO/founder interviews and discussions
- **Industry podcasts** - Analysis, trends, competitive commentary
- **Company mentions** - Brand awareness, sentiment, reputation tracking
- **Thought leadership** - Track company experts and their insights

**Implementation:**
- Use podcast RSS feeds or Podcast Index API
- Search episode titles and descriptions for keywords
- Fetch transcripts when available (many podcasts provide them)
- Process transcripts as text intelligence
- Fall back to episode descriptions when transcripts unavailable
- AI extracts key quotes and themes
- Link to episode

**Technical Details:**
- **API Options:**
  - **Podcast Index API** - Open database, free tier available
  - **Listen Notes API** - Good search, 100 free requests/month
  - **Direct RSS feeds** - Free, no API needed for specific shows
- **Transcripts:**
  - Some podcasts include transcripts in RSS feeds
  - Some provide transcript URLs in show notes
  - Services like Podcast Transcript API
  - Many professional podcasts have transcripts available
- **Processing:** Treat transcript as `content`, episode title as `title`
- **Source tier:** 3 (secondary - audio content)

**Advantages of Transcript Approach:**
- ✅ No speech-to-text costs
- ✅ Fast text processing
- ✅ Searchable content
- ✅ Extract exact quotes
- ✅ Uses existing AI pipeline

**Limitations:**
- Not all podcasts provide transcripts
- May miss episodes without transcripts
- Transcript quality varies by podcast

**Configuration (per customer):**
```yaml
podcast_feeds:
  - name: "Industry Weekly"
    rss_url: "https://podcast.example.com/feed"
    check_transcripts: true
  - name: "Tech Leaders Podcast"
    rss_url: "https://techleaders.com/feed"
    check_transcripts: true
podcast_search_terms:
  - "company name CEO"
  - "industry trends 2025"
transcript_sources:
  - "rss_feed"        # Look in RSS feed
  - "show_notes"      # Check show notes for transcript links
  - "description"     # Use description if no transcript
```

**Collection Flow:**
1. Monitor RSS feeds or search via Podcast Index API
2. Find episodes matching keywords
3. Check for transcript availability:
   - In RSS feed enclosure
   - In show notes/description
   - Via transcript service
4. If transcript found: Create full intelligence item
5. If no transcript: Create item with description only (lower priority)
6. AI processes transcript for key insights
7. Display in feed with podcast artwork and episode link

**Transcript Sources by Podcast Network:**
- **NPR, BBC** - Usually provide transcripts
- **Gimlet, Wondery** - Often have transcripts
- **Independent podcasts** - Varies widely
- **Corporate podcasts** - Often have transcripts (marketing materials)

**Phased Approach:**
1. **Phase 1** - Monitor specific RSS feeds with transcripts
2. **Phase 2** - Add Podcast Index search
3. **Phase 3** - Integrate transcript services for broader coverage

---

#### 8. Add Bluesky as a Social Media Source
**Status:** Pending
**Effort:** Medium
**Description:** Integrate Bluesky social network as an intelligence source for company mentions, executive posts, and industry discussions.

**Use Cases:**
- Monitor company official accounts on Bluesky
- Track executive posts and announcements
- Follow industry discussions and trends
- Capture real-time customer sentiment
- Monitor competitor activity

**Implementation:**
- **Bluesky AT Protocol API** - Uses atproto (Authenticated Transfer Protocol)
- **Firehose Integration** - Real-time stream of posts
- **Search API** - Keyword-based post search
- **Profile Monitoring** - Track specific user profiles
- **Thread Collection** - Capture full conversation threads

**Technical Details:**
- **API:** AT Protocol (open, decentralized)
- **Authentication:** API key or OAuth
- **Rate Limits:** TBD (more generous than Twitter)
- **Search:** Full-text search with keyword filtering
- **Collection Strategy:** Similar to Reddit (search + profile monitoring)

**Configuration (per customer):**
```yaml
bluesky_enabled: true
bluesky_handles:
  - "@company.bsky.social"
  - "@ceo.bsky.social"
bluesky_search_terms:
  - "company name"
  - "product name"
bluesky_min_likes: 5  # Engagement filter
bluesky_min_reposts: 2
```

**Advantages:**
- ✅ Open protocol (no API restrictions like Twitter)
- ✅ Growing user base of tech-savvy professionals
- ✅ Better API access than Twitter/X
- ✅ Decentralized (more stable than centralized platforms)
- ✅ Strong tech industry presence

**Collection Flow:**
1. Search Bluesky for keywords related to customer
2. Monitor configured handles (company, executives)
3. Filter by engagement (likes, reposts, replies)
4. Capture thread context (replies, quotes)
5. AI processes posts like other social media
6. Display in feed with Bluesky branding

**Source Tier:** 5 (Community/Social Media)

**Comparison to Twitter:**
- More open API
- Better developer access
- Growing platform (early adopter advantage)
- Tech-heavy user base (ideal for B2B tech intelligence)

---

#### 9. Add Mastodon as a Social Media Source
**Status:** Pending
**Effort:** Medium
**Description:** Integrate Mastodon (Fediverse) as an intelligence source for company mentions, executive posts, and industry discussions across decentralized instances.

**Use Cases:**
- Monitor company and executive accounts on Mastodon
- Track industry discussions across Fediverse instances
- Follow tech community conversations
- Capture sentiment from privacy-conscious audiences
- Monitor open-source and developer communities

**Implementation:**
- **Mastodon API** - RESTful API available on all instances
- **Timeline Monitoring** - Public, local, and federated timelines
- **Search API** - Keyword-based toot search (instance-dependent)
- **Account Monitoring** - Track specific user accounts
- **Thread Collection** - Capture full conversation threads with replies

**Technical Details:**
- **API:** Mastodon REST API v1/v2 (standardized across instances)
- **Authentication:** OAuth 2.0 or API token (per instance)
- **Rate Limits:** Instance-specific (typically generous, ~300 requests/5min)
- **Search:** Full-text search (availability varies by instance)
- **Multi-Instance:** Can monitor multiple instances simultaneously
- **Collection Strategy:** Similar to Twitter (account monitoring + hashtag search)

**Configuration (per customer):**
```yaml
mastodon_enabled: true
mastodon_instances:
  - instance: "mastodon.social"
    accounts:
      - "@company@mastodon.social"
      - "@ceo@mastodon.social"
  - instance: "fosstodon.org"
    accounts:
      - "@techteam@fosstodon.org"
mastodon_hashtags:
  - "#companyname"
  - "#productname"
  - "#industryterm"
mastodon_min_favorites: 5  # Engagement filter
mastodon_min_boosts: 2
mastodon_include_replies: false  # Include reply threads
```

**Advantages:**
- ✅ Open source and decentralized (no single point of failure)
- ✅ Well-documented, standardized API across instances
- ✅ No API restrictions or paywalls
- ✅ Strong tech and open-source community presence
- ✅ Privacy-focused user base (quality discussions)
- ✅ Growing platform, especially among developers
- ✅ Free API access with generous rate limits

**Collection Flow:**
1. Connect to configured Mastodon instances
2. Monitor account timelines for configured handles
3. Search hashtags and keywords (if instance supports it)
4. Filter by engagement (favorites, boosts, replies)
5. Capture thread context (replies, boosts, mentions)
6. AI processes toots like other social media
7. Display in feed with Mastodon branding and instance info

**Source Tier:** 5 (Community/Social Media)

**Multi-Instance Strategy:**
- Each instance is independent with its own API
- Monitor multiple instances to capture broader Fediverse conversations
- Some large instances: mastodon.social, fosstodon.org, techhub.social, hachyderm.io
- Instance-specific rate limits and features

**Comparison to Twitter/Bluesky:**
- More decentralized than Bluesky (multiple instances vs single protocol)
- Better API access than Twitter (no fees, no restrictions)
- Smaller but highly engaged audience
- Strong developer and open-source community
- Better privacy controls for users

---

#### 10. Fix and Test Reddit Data Source
**Status:** ✅ Complete
**Effort:** Medium
**Description:** Get Reddit integration working reliably for community discussions and sentiment.

**Completed Improvements:**
- ✅ Migrated from synchronous PRAW to Async PRAW (no async warnings)
- ✅ Implemented engagement filtering (min 5 upvotes OR 3 comments)
- ✅ Added AI-powered thread summarization for large discussions (≥10 comments)
- ✅ Quality filtering (skip deleted/removed posts, spam)
- ✅ Smart content strategy: small threads get top comments verbatim, large threads get AI summary
- ✅ Metadata tracking (subreddit, author, score, comment count, ai_summarized flag)
- ✅ Tested successfully with IBM subreddit (13 items collected)

**Technical Details:**
- Uses `asyncpraw` for proper async support
- AI summarization via Claude (500 token max)
- Summarizes top 15 comments by score
- Fallback to simple concatenation if AI fails
- Rate limiting: 60 requests per window
- Lookback: 7 days
- Search limit: 10 posts per subreddit per keyword

**Example Output:**
- Threads with 10-43 comments successfully summarized
- Summaries include topic, sentiment, key points, consensus
- Business intelligence suitable format

---

### Priority 2: Intelligence & Learning

#### 11. Platform Settings Configuration (Expanded from Daily Briefing Prompts)
**Status:** ✅ Complete
**Effort:** Medium → Large (expanded scope)
**Description:** Comprehensive platform settings UI allowing configuration of daily briefings, AI models, collection schedules, clustering, and collector-specific settings.

**Implemented Features:**

**Daily Briefing Settings:**
- ✅ 6 prompt templates (Standard, Executive, Sales-focused, Risk-focused, Technical, Custom)
- ✅ Custom prompt editor with preview
- ✅ Briefing style options (length: brief/standard/detailed, tone: casual/professional/technical)
- ✅ Focus areas checkboxes (competitive intel, opportunities, risks, trends, product updates, market changes)
- ✅ Real-time prompt preview
- ✅ Stored in `platform_settings` table

**AI Configuration:**
- ✅ Claude model selection (Sonnet 4.5, Sonnet 3.5, Opus, Haiku)
- ✅ Embedding model selection (MiniLM-L6-v2, MPNet-Base-v2, BGE-Small)
- ✅ Warning about model change impacts

**Collection & Retention:**
- ✅ Toggle hourly collection on/off
- ✅ Toggle daily comprehensive collection on/off
- ✅ Configurable daily collection time (0-23 hours with friendly labels)
- ✅ Data retention period (30/60/90/180/365 days)
- ✅ Story clustering enable/disable
- ✅ Similarity threshold slider (30-80% with guidance text)
- ✅ Clustering time window (24-168 hours)

**Collector-Specific Settings (Reddit):**
- ✅ Minimum upvotes threshold (engagement filter)
- ✅ Minimum comments threshold (engagement filter)
- ✅ Large thread AI summarization threshold
- ✅ Max comments to analyze for AI summary
- ✅ Posts per subreddit limit
- ✅ Lookback days (1/3/7/14/30)

**Technical Implementation:**
- ✅ `PlatformSettings` table with JSON key-value storage
- ✅ Settings API endpoints (`/api/settings/platform` GET/PUT)
- ✅ 4-tab modal UI (Daily Briefing, AI Config, Collection & Retention, Collector Settings)
- ✅ Migration script (`tools/add_platform_settings.py`)
- ✅ Hot-reloadable settings (clustering, Reddit collector)
- ✅ Settings button in header
- ✅ Falls back to defaults if not configured
- ✅ Extensible architecture for adding more collector settings

**Total Configurable Parameters:** 25+

---

#### 12. Deep Research Mode
**Status:** Pending
**Effort:** Large
**Description:** AI-powered deep research tool to comprehensively analyze new customers or significant changes in customer circumstances. Generates detailed research reports in the UI.

**Primary Use Cases:**
- **New Customer Onboarding** - Rapidly understand a newly added customer's market position, recent news, competitive landscape
- **Change in Circumstances** - Deep dive when major events occur (merger, executive change, product launch, crisis)
- **Competitive Analysis** - Comprehensive research on competitors added to tracking
- **Market Analysis** - In-depth understanding of industry trends affecting the customer
- **Due Diligence** - M&A research, investment analysis, partnership evaluation

**Features:**

**Trigger Mechanisms:**
- **Manual Trigger** - "Deep Research" button on customer page
- **Ad-hoc Query** - Free-form research questions (e.g., "What are Tesla's recent AI initiatives?")
- **On-Demand** - Research specific topics, people, or events
- **Scheduled** - Optional periodic deep dives (quarterly customer reviews)

**Data Collection:**
- **Existing Intelligence** - Analyze all collected items for the customer
- **Fresh Collection** - Trigger immediate collection from all active sources
- **Extended Sources** - Go beyond normal sources:
  - Web search (Google/Bing API) for recent articles
  - Company website deep crawl
  - SEC filings (for public companies)
  - Patent databases
  - Academic papers
  - Industry reports
- **Cross-Reference** - Analyze competitors and related entities simultaneously

**AI-Powered Analysis:**
- **Multi-Step Research Agent** - Claude-powered agentic workflow:
  1. Understand research objective
  2. Identify key areas to investigate
  3. Gather and synthesize information
  4. Cross-reference and verify facts
  5. Generate comprehensive report
- **Source Synthesis** - Combine insights from 50+ sources into coherent narrative
- **Timeline Construction** - Chronological view of key events
- **Sentiment Analysis** - Track sentiment trends over time
- **Entity Extraction** - Identify key people, products, partnerships, locations
- **Competitive Positioning** - Compare against competitors on multiple dimensions

**Report Structure:**
1. **Executive Summary** (2-3 paragraphs)
   - Key findings and takeaways
   - Critical developments
   - Recommended actions

2. **Company Overview**
   - Business model and operations
   - Market position and size
   - Recent performance metrics
   - Leadership team

3. **Recent Developments** (Last 90 days)
   - Product launches
   - Strategic initiatives
   - Executive changes
   - Financial results
   - Partnerships and M&A

4. **Competitive Landscape**
   - Key competitors
   - Competitive advantages/disadvantages
   - Market share analysis
   - Differentiation strategies

5. **Sentiment & Public Perception**
   - Overall sentiment trend
   - Media coverage analysis
   - Social media sentiment
   - Customer feedback themes

6. **Opportunities & Risks**
   - Growth opportunities
   - Emerging threats
   - Strategic challenges
   - Market trends impact

7. **Key People & Relationships**
   - Leadership profiles
   - Board composition
   - Strategic partnerships
   - Industry connections

8. **Timeline View**
   - Interactive timeline of major events
   - Visual representation of company evolution
   - Milestone markers

9. **Source Summary**
   - Number of sources analyzed
   - Source diversity breakdown
   - Confidence indicators
   - Data gaps identified

**UI/UX:**
- **Research Tab** - New tab on customer page alongside "Intelligence" and "Executive Summary"
- **Research History** - View past research reports with timestamps
- **Progress Indicator** - Real-time progress during research generation
  - "Collecting data from sources... (45/100)"
  - "Analyzing 234 items..."
  - "Generating report sections..."
- **Interactive Report** - Expandable sections, citations, related items
- **Export Options** - PDF, markdown, email
- **Refresh Button** - Update research with latest data

**Technical Implementation:**

**Backend:**
- **Research API** - `/api/research/generate/{customer_id}`
  - POST to trigger new research
  - Query params: `scope` (30/60/90 days), `depth` (quick/standard/deep)
  - Background job (long-running)
- **Research Storage** - New table `research_reports`
  - customer_id, generated_at, scope, depth
  - report_json (structured data)
  - status (pending/processing/complete/failed)
- **Agentic Workflow** - Multi-step Claude agent:
  - Tool use for querying database
  - Web search integration
  - Iterative refinement
  - Source citation tracking

**Frontend:**
- **Research Component** - New React component
- **Report Renderer** - Markdown + interactive elements
- **Timeline Visualization** - D3.js or similar
- **Export Function** - PDF generation (puppeteer)

**Configuration (per research request):**
```yaml
research_config:
  scope_days: 90          # How far back to analyze
  depth: "deep"           # quick/standard/deep
  include_competitors: true
  extended_sources: true   # Go beyond normal collection
  fresh_collection: true   # Trigger new collection first
  sections:               # Which sections to include
    - executive_summary
    - company_overview
    - recent_developments
    - competitive_landscape
    - sentiment_analysis
    - opportunities_risks
    - timeline
```

**Performance Considerations:**
- **Background Processing** - Long-running job (5-15 minutes)
- **Caching** - Cache research reports, refresh on demand
- **Progressive Loading** - Show sections as they complete
- **Rate Limiting** - Limit concurrent research jobs

**Future Enhancements:**
- **Research Templates** - Pre-defined research types (competitor analysis, market entry, crisis response)
- **Comparison Mode** - Side-by-side research on multiple companies
- **Chat Interface** - Ask follow-up questions about the research
- **Auto-Update** - Automatically refresh research when significant events occur
- **Research Sharing** - Share reports with team members
- **Custom Sections** - User-defined research areas
- **Multi-Customer Research** - Industry-wide analysis across customers

**Example Workflow:**
1. User adds new customer "Acme Corp" or major event occurs
2. Clicks "Deep Research" button
3. Selects scope (90 days) and depth (deep)
4. System triggers fresh collection from all sources
5. AI agent analyzes 200+ items + web search results
6. Report generated in 8 minutes with 9 comprehensive sections
7. User reviews timeline, competitive analysis, opportunities
8. Exports PDF report for executive team
9. Research auto-saved and accessible in history

---

#### 13. Design Relevance Feedback Loop
**Status:** Pending
**Effort:** Large
**Description:** Use collected data about user actions (ignore/keep) to continuously improve AI filtering and relevance scoring.

**Approach:**
- **Track User Actions:**
  - Items ignored (deleted)
  - Items kept (not ignored)
  - Search queries
  - Filter preferences
  - Time spent on items

- **Build Feedback Dataset:**
  - Store user actions in database
  - Label ignored items as "not relevant"
  - Label kept items as "relevant"
  - Track patterns per customer

- **Improve AI Over Time:**
  - Fine-tune Claude prompts based on patterns
  - Adjust priority scoring algorithm
  - Learn customer-specific preferences
  - Auto-suggest better keywords
  - Identify unreliable sources

- **Implementation Ideas:**
  - Add `user_feedback` table (item_id, action, timestamp)
  - Weekly analysis job to identify patterns
  - A/B testing for prompt improvements
  - Customer-specific AI prompt customization
  - Report on AI accuracy metrics

---

#### 30. Automatic Entity & Keyword Discovery
**Status:** Pending
**Effort:** Large
**Description:** AI-powered system to automatically identify new entities (people, companies, products, keywords) from collected intelligence that should be added to monitoring configuration.

**Business Value:**
- Discover emerging topics without manual keyword updates
- Identify new executives, partners, competitors automatically
- Surface new product names and industry terms
- Reduce manual configuration overhead
- Ensure comprehensive coverage as landscape evolves

**Use Cases:**
- **New People** - Executive hires, board appointments, key hires mentioned frequently
- **New Companies** - Competitors, partners, acquisition targets, emerging startups
- **New Products** - Product launches, service names, brand names
- **New Keywords** - Emerging technologies, industry buzzwords, trending topics
- **New Locations** - New offices, markets, geographic expansion
- **New Events** - Conferences, initiatives, programs mentioned repeatedly

**Implementation:**

**Phase 1: Entity Extraction (2-3 months)**
- **Named Entity Recognition (NER)** - Extract people, organizations, products from intelligence
- **Entity Database** - Store discovered entities with metadata
- **Frequency Tracking** - Count mentions across intelligence items
- **Context Analysis** - Understand entity relationships and significance
- **Entity Types:**
  - PERSON - Names of individuals
  - ORGANIZATION - Companies, institutions
  - PRODUCT - Product/service names
  - TECHNOLOGY - Technical terms, frameworks
  - LOCATION - Cities, countries, regions
  - EVENT - Conferences, programs, initiatives

**Phase 2: Significance Scoring (1-2 months)**
- **Mention Frequency** - How often entity appears
- **Recency** - Recent vs old mentions
- **Context Importance** - Mentioned in headlines vs passing reference
- **Source Authority** - Mentioned in tier 1 sources vs social media
- **Relationship Strength** - How closely related to customer
- **Trend Detection** - Increasing mentions over time
- **Confidence Score** - AI confidence in entity relevance

**Scoring Algorithm:**
```python
significance_score = (
    mention_count * 0.3 +
    recency_boost * 0.2 +
    context_importance * 0.25 +
    source_tier_weight * 0.15 +
    trend_velocity * 0.1
)
```

**Phase 3: Discovery UI (2-3 weeks)**
- **Discoveries Tab** - New section in customer view
- **Entity Cards** - Show discovered entities with:
  - Entity name and type
  - Significance score and trend indicator
  - First seen / last seen dates
  - Mention count and timeline
  - Sample intelligence items mentioning entity
  - "Add to Monitoring" button
- **Filter/Sort** - By entity type, score, date, trending
- **Bulk Actions** - Add multiple entities at once
- **Dismiss/Ignore** - Mark entities as not relevant

**Phase 4: Automated Suggestions (1-2 months)**
- **Proactive Notifications** - Alert when high-significance entities discovered
- **Auto-Add Rules** - Automatically add entities above threshold
- **Smart Categorization** - Suggest which config field to add to:
  - High-level executive → LinkedIn monitoring
  - Competitor company → competitors list
  - Industry term → keywords
  - Product name → priority keywords
- **Review Queue** - Weekly digest of discoveries for approval

**Phase 5: Learning & Refinement (Ongoing)**
- **User Feedback Loop** - Track which suggestions are accepted/rejected
- **Pattern Learning** - Learn customer-specific entity preferences
- **False Positive Reduction** - Improve filtering based on dismissals
- **Entity Relationships** - Map connections between entities
- **Temporal Analysis** - Detect entity lifecycle (emerging → established → declining)

**Data Model:**
```yaml
discovered_entities:
  - id: "ent_001"
    customer_id: 123
    entity_name: "Jane Smith"
    entity_type: "PERSON"
    first_seen: "2025-11-01"
    last_seen: "2025-11-10"
    mention_count: 15
    significance_score: 0.87
    trending: true
    confidence: 0.92
    context_summary: "New CFO hired, mentioned in 15 articles"
    intelligence_items: [456, 789, 1011, ...]
    status: "suggested"  # suggested, added, dismissed
    suggested_field: "linkedin_user_profiles"  # Where to add

keywords_discovered:
  - id: "kw_001"
    customer_id: 123
    keyword: "quantum computing initiative"
    first_seen: "2025-11-05"
    mention_count: 8
    significance_score: 0.73
    trend_velocity: 0.15  # Growing 15% per week
    context: "Customer launched new quantum computing program"
    status: "suggested"
```

**API Endpoints:**
- `GET /api/discoveries/{customer_id}` - List discovered entities
- `GET /api/discoveries/{customer_id}/trending` - Trending entities
- `POST /api/discoveries/{discovery_id}/add` - Add to monitoring
- `POST /api/discoveries/{discovery_id}/dismiss` - Mark as irrelevant
- `GET /api/discoveries/{customer_id}/suggestions` - Auto-suggestions

**UI Mockup:**
```
┌─ Discoveries (12 new) ────────────────────────────────┐
│ Filter: [All] [People] [Companies] [Keywords] [Trending] │
│                                                           │
│ 🔥 Jane Smith (PERSON)                      Score: 0.87  │
│    New CFO • 15 mentions • Trending ↗                    │
│    First seen 10 days ago • Last seen today              │
│    Mentioned in: Reuters, TechCrunch, LinkedIn           │
│    [Add to LinkedIn Monitoring] [Dismiss] [View Items]   │
│                                                           │
│ 🔥 Quantum Computing Initiative (KEYWORD)   Score: 0.73  │
│    Product/Technology • 8 mentions • Trending ↗          │
│    Customer launched new R&D program                     │
│    [Add to Priority Keywords] [Dismiss]                  │
│                                                           │
│ 📈 Acme Security Corp (ORGANIZATION)        Score: 0.65  │
│    Potential Competitor • 12 mentions                    │
│    Mentioned alongside customer in 5 articles            │
│    [Add to Competitors] [Dismiss]                        │
└───────────────────────────────────────────────────────────┘
```

**Technical Implementation:**

**NER Approaches:**
- **Claude AI** - Use Claude's entity extraction capabilities (current approach)
- **spaCy NER** - Fast, pre-trained NER models (en_core_web_lg)
- **Hybrid** - Claude for context + spaCy for speed
- **Custom Training** - Fine-tune on business intelligence corpus

**Entity Linking:**
- Link discovered entities to external sources (LinkedIn, Wikipedia, Crunchbase)
- Enrich entity data with additional context
- Verify entity identity (distinguish John Smith A from John Smith B)

**Storage:**
- New tables: `discovered_entities`, `entity_mentions`
- Many-to-many: entities ↔ intelligence_items
- Indexed by customer, type, score, status

**Performance:**
- Background processing (don't slow down collection)
- Incremental entity extraction (process new items only)
- Cached entity database for fast queries
- Debounce trending calculations (hourly)

**Configuration:**
```yaml
entity_discovery:
  enabled: true
  auto_extract: true
  min_mentions: 3  # Minimum mentions to surface
  min_score: 0.5   # Minimum significance score
  auto_add_threshold: 0.9  # Auto-add entities above this score
  entity_types: ["PERSON", "ORGANIZATION", "PRODUCT", "TECHNOLOGY"]
  notification_enabled: true
  weekly_digest: true
```

**Example Workflow:**
1. Intelligence collected: "Acme Corp announces Jane Smith as new CFO"
2. AI extracts entities: "Jane Smith" (PERSON), "CFO" (TITLE)
3. Entity stored with metadata, linked to intelligence item
4. Over next week, Jane mentioned in 15 more articles
5. Significance score climbs to 0.87
6. System suggests: "Add Jane Smith to LinkedIn monitoring?"
7. User clicks "Add" → Jane's profile automatically added to config
8. Future collections now monitor Jane's LinkedIn posts
9. User receives notifications about Jane's activities

**Integration Points:**
- **LinkedIn Collector** - Auto-add discovered executives
- **Customer Config** - Update keywords, competitors, etc.
- **Analytics** - Track discovery accuracy and acceptance rate
- **Notifications** - Alert on high-value discoveries

**Success Metrics:**
- Entities discovered per week
- Discovery acceptance rate (% added to monitoring)
- False positive rate (% dismissed)
- Coverage improvement (new entities missed by manual config)
- Time saved on manual configuration

**Future Enhancements:**
- **Entity Timeline** - Visualize entity mentions over time
- **Entity Relationships** - Graph of connections between entities
- **Cross-Customer Insights** - Industry-wide entity trends
- **Entity Profiles** - Dedicated pages for each discovered entity
- **Smart Alerts** - Alert when tracked entities interact (merger, partnership)
- **Entity Sentiment** - Track sentiment toward discovered entities
- **Multi-Language** - Detect entities in non-English content
- **Entity Disambiguation** - Resolve name conflicts (same name, different person)

**Challenges:**
- Name ambiguity (common names, nicknames)
- Context understanding (is "Apple" the company or fruit?)
- Noise filtering (one-off mentions vs significant entities)
- Entity lifecycle management (when to stop tracking)
- Privacy considerations (tracking individuals)

**Privacy & Ethics:**
- Only suggest publicly mentioned individuals
- Respect LinkedIn privacy settings
- Allow users to opt-out of entity tracking
- Clear about what data is collected
- Comply with data protection regulations

---

### Priority 3: User Experience

#### 14. Fix Mobile Browser Layout
**Status:** ✅ Complete
**Effort:** Small
**Description:** Fix responsive layout issues where mobile browsers only show the executive summary panel instead of the main feed.

**Current Issue:**
- On mobile browsers, the two-column layout breaks
- Executive summary panel appears first (due to CSS ordering)
- Main feed is hidden or pushed below the fold
- Users cannot access the primary intelligence feed on mobile

**Tasks:**
- Fix CSS media queries for mobile breakpoint
- Ensure main feed displays first on mobile
- Make executive summary collapsible or below feed on mobile
- Test on various mobile devices (iOS Safari, Chrome Android)
- Improve touch interactions (swipe, tap targets)
- Optimize mobile performance (lazy loading, smaller images)

**Acceptance Criteria:**
- Main feed is primary view on mobile
- All functionality accessible on mobile
- Responsive design works on screens 320px-768px wide
- Touch-friendly interface elements

---

#### 15. Implement Story Clustering & Intelligent Deduplication
**Status:** ✅ Complete
**Effort:** Medium
**Description:** Reduce feed clutter by intelligently grouping similar stories from multiple sources into clusters, surfacing only the most relevant and authoritative content.

**Current Problem:**
- Same news story appears 10+ times from different sources (Google News, Reuters, TechCrunch, etc.)
- Reddit discussions duplicate news stories
- Feed cluttered with repetitive content
- Hard to identify truly unique/new intelligence
- User fatigue from scrolling through duplicates

**Proposed Solution: Multi-Layer Story Clustering**

**Phase 1: Backend Story Clustering** (In Progress)
- Add `cluster_id` field to IntelligenceItem model
- Use existing vector embeddings for similarity detection
- Group items within 48 hours with >85% semantic similarity
- Assign most authoritative source as cluster primary
- Track cluster metadata (source count, types)

**Phase 2: Source Tier System**
- Tier 1 (Official): Press releases, company newsrooms, executive LinkedIn
- Tier 2 (Primary): Reuters, Bloomberg, AFP, WSJ, original reporting
- Tier 3 (Secondary): TechCrunch, The Verge, industry blogs
- Tier 4 (Aggregators): Google News, MSN, Yahoo
- Tier 5 (Community): Reddit, Twitter, forums
- Priority rules: Prefer Tier 1-2, group Reddit with parent stories

**Phase 3: Enhanced Priority Scoring**
- Novelty factor: First time seeing this story (+0.2)
- Duplicate penalty: Already have 3+ similar items (-0.3)
- Source diversity bonus: First item from this source type (+0.1)

**Phase 4: UI View Modes**
- **Smart Feed (Default)**: Story clusters, one item per story, expandable
- **Full Feed**: Everything, no clustering, filter by source
- **Digest View**: Ultra-compact, headlines only

**Implementation Details:**
```
[Primary Item - Most Authoritative]
📰 IBM Announces 8,000 Layoffs, AI Restructuring
   TechCrunch · 2 hours ago · Priority: 0.9
   [View 4 other sources: Reuters, Bloomberg, AFP, WSJ]
   [💬 2 Reddit discussions: r/IBM (33), r/technology (127)]
```

**Database Changes:**
- Add `cluster_id` (String, nullable, indexed)
- Add `is_primary` (Boolean, default False)
- Add `source_tier` (String: official/primary/secondary/aggregator/social)
- Add `cluster_member_count` (Integer, for quick display)

**Clustering Algorithm:**
1. New item arrives with embedding
2. Query recent items (48 hours) for similar embeddings (>0.85 similarity)
3. If match found: assign to existing cluster, update primary if higher tier
4. If no match: create new cluster_id (UUID)
5. Update cluster member counts

**API Changes:**
- Feed endpoint: Add `?cluster=true` parameter (default true)
- Return cluster metadata with each item
- Add `/api/feed/cluster/{cluster_id}` to get all items in cluster

**Completed Implementation:**
- ✅ Added clustering fields to IntelligenceItem model (`cluster_id`, `is_cluster_primary`, `source_tier`)
- ✅ Implemented vector similarity-based clustering (>0.50 threshold, 96-hour window)
- ✅ Smart Feed shows only primary items (one per story)
- ✅ Full Feed shows all items with clustering metadata
- ✅ API endpoint `/api/feed/cluster/{cluster_id}` to expand clusters
- ✅ Source tier system for prioritizing authoritative sources
- ✅ Backfill clustering via hermes-diag tool

**Benefits Achieved:**
- ✅ Reduces visual clutter by 70-80%
- ✅ Preserves source diversity (expandable clusters)
- ✅ Highlights official/authoritative sources
- ✅ Links Reddit discussions with news stories
- ✅ Improves information discovery
- ✅ Reduces user fatigue

**Future Enhancements:**
- Story timeline view (how story evolved)
- Multi-source AI summarization
- Source quality ratings based on user feedback
- Cross-cluster relationship detection

---

#### 16. Collection Error Monitoring & Alert System
**Status:** ✅ Complete
**Effort:** Small
**Description:** Real-time monitoring and UI alerts for data collection failures and authentication issues.

**Problem Solved:**
- No visibility when data collectors fail (Reddit, LinkedIn, etc.)
- Auth issues go unnoticed until users check logs
- Silent failures lead to missing intelligence
- Users need proactive notifications for collection problems

**Implementation:**
- **CollectionStatus Table:** Tracks status per source per customer
  - Status: success, error, auth_required
  - Error message and error count
  - Last run and last success timestamps
- **API Endpoint:** `/api/feed/collection-errors` returns active errors
- **Error Banner Component:** Sticky banner at top of UI
  - Yellow banner for auth_required (e.g., LinkedIn logout)
  - Red banner for general errors
  - Shows source type, error message, and error count
  - Dismissible with animation
  - Auto-fetches on component mount
- **Backend Tracking:** Collectors update status after each run

**Technical Details:**
- Backend: `app/models/database.py` (CollectionStatus model)
- Backend: `app/api/feed.py:101` (collection-errors endpoint)
- Frontend: `frontend/src/components/ErrorBanner.jsx`
- Frontend: `frontend/src/styles/ErrorBanner.css`

**Benefits:**
- ✅ Immediate visibility of collection failures
- ✅ Proactive notification of auth issues
- ✅ Better user experience with clear error messages
- ✅ Helps users resolve issues quickly

---

#### 17. Customer Management in UI
**Status:** ✅ Complete
**Effort:** Medium
**Description:** Full customer management interface with database-first approach and YAML import/export.

**Implemented Features:**

**Customer Management UI:**
- ✅ Customer tabs in header for quick switching
- ✅ Add Customer wizard modal with multi-step form
- ✅ Edit Customer modal (gear icon in customer header)
- ✅ Delete customer with confirmation dialog
- ✅ Real-time validation and error messages
- ✅ All YAML config fields represented in UI

**Customer Configuration:**
- ✅ Basic info (name, domain, keywords, competitors, stock symbol)
- ✅ Per-customer data source toggles (news, RSS, LinkedIn, stock, Reddit, Twitter, GitHub, HackerNews, web scraping)
- ✅ Collection config:
  - Priority keywords
  - Reddit subreddits
  - RSS feed URLs
  - LinkedIn user profiles (with description field)
  - GitHub repos and organizations
  - Web scraping sources with CSS selectors
- ✅ Description and notes fields
- ✅ Social media handles (Twitter, LinkedIn company)

**API Endpoints:**
- ✅ GET `/api/customers` - List all customers
- ✅ GET `/api/customers/{id}` - Get customer details
- ✅ POST `/api/customers` - Create customer
- ✅ PUT `/api/customers/{id}` - Update customer
- ✅ DELETE `/api/customers/{id}` - Delete customer

**Data Management:**
- ✅ Database is source of truth
- ✅ hermes-diag import-config/export-config commands
- ✅ Custom file path support (--file/-f flag)
- ✅ Bidirectional sync (YAML ↔ DB)
- ✅ Proper data structure (nested YAML, flat DB)
- ✅ All collection config fields synced

**Technical Implementation:**
- ✅ Customer CRUD API in `app/api/customers.py`
- ✅ Modal components (AddCustomerModal, CustomerEditModal)
- ✅ Customer tabs with gear icon
- ✅ Form validation and error handling
- ✅ Data structure normalization (YAML nested → DB flat)
- ✅ Import/export via hermes-diag CLI

---

### Priority 4: Distribution & Notifications

#### 18. Add Email Digest Output
**Status:** Pending
**Effort:** Medium
**Description:** Send automated email digests with daily/weekly summaries of intelligence.

**Features:**
- **Daily Digest:**
  - Executive summary from AI
  - Top 5-10 high-priority items
  - Category breakdown
  - Delivered at configurable time (e.g., 8 AM)

- **Weekly Digest:**
  - Weekly executive summary
  - Top stories of the week
  - Trend analysis
  - Competitor activity highlights

**Tasks:**
- Choose email service (SendGrid, AWS SES, SMTP)
- Design email templates (HTML + plain text)
- Add email configuration to customer config
- Create digest generation job
- Add unsubscribe/preferences management
- Test email deliverability

---

#### 19. Add Slack Notification Integration
**Status:** Pending
**Effort:** Medium
**Description:** Send real-time notifications to Slack channels for high-priority intelligence.

**Features:**
- **Real-time Alerts:**
  - High-priority items (score >= 0.8)
  - Priority keyword matches
  - Competitor mentions
  - Executive changes

- **Daily Summaries:**
  - Post daily summary to Slack channel
  - Interactive buttons (mark as read, ignore)
  - Thread discussions

- **Customization:**
  - Per-customer Slack channels
  - Configurable alert thresholds
  - Rich message formatting with embeds

**Tasks:**
- Create Slack app and bot
- Implement Slack webhook integration
- Design message templates
- Add Slack config to customer settings
- Support multiple workspaces/channels
- Add interactive elements (buttons, threads)

---

#### 20. Move Australian News Sources Configuration into Platform Settings
**Status:** ✅ Complete
**Effort:** Small
**Description:** Move Australian news configuration from hardcoded/YAML settings into the Platform Settings Modal for better management.

**Implemented Features:**
- ✅ Backend schema for `australian_news_sources` in platform settings
- ✅ Default configuration with 6 Australian news sources (ABC News, Guardian AU, The Australian, SMH, The Age, News.com.au)
- ✅ Collector updated to load from platform settings with database fallback
- ✅ UI section in Collector Settings tab with full CRUD operations
- ✅ Per-source enable/disable toggles
- ✅ Editable source names and RSS feed URLs
- ✅ Add/remove news sources dynamically
- ✅ Multi-feed support per source

**Technical Implementation:**
- Backend: `app/api/settings.py` (schema and endpoints)
- Backend: `app/collectors/australian_news_collector.py` (loads from DB)
- Frontend: `PlatformSettingsModal.jsx` (Collector Settings tab)
- Sources stored as JSON array with name, enabled flag, and feeds array

---

### Priority 5: UX Polish & Optimization

#### 21. Add Tooltips to UI Buttons
**Status:** ✅ Complete
**Effort:** Small
**Description:** Add helpful tooltips to all interactive buttons and controls to improve user experience and discoverability.

**Implemented Tooltips:**
- ✅ Collect button (trigger collection for customer)
- ✅ Refresh feed button (manual refresh)
- ✅ Settings button (platform configuration)
- ✅ Customer edit button (edit customer settings)
- ✅ Trigger Collection button (all customers)
- ✅ View Source link
- ✅ Various other interactive elements

**Implementation:**
- Uses HTML title attribute for browser-native tooltips
- Tooltips appear on hover
- Clear, descriptive text for each button

---

#### 22. Improve Alert Clearing/Dismissing Behavior
**Status:** ✅ Complete
**Effort:** Small
**Description:** Better error banner dismissal with "dismiss all" option and persistent dismissals.

**Implemented Features:**
- ✅ Error banners can be dismissed
- ✅ Dismissals persist across page refreshes
- ✅ Clear UX for dismissing alerts
- ✅ Improved error banner behavior

---

#### 23. Fix Items Being Marked as Irrelevant
**Status:** ✅ Monitoring (Working Well)
**Effort:** Medium
**Description:** Improve AI categorization accuracy to reduce false positives (relevant items marked as unrelated/advertisement).

**Analysis Completed:**
- ✅ Created analysis script (`tools/analyze_irrelevant_items.py`)
- ✅ Analyzed current categorization patterns
- ✅ Checked for false positives (high priority items marked as irrelevant)
- ✅ Reviewed source types producing problematic items
- ✅ Current AI performance appears satisfactory

**Script Features:**
- Category distribution breakdown with percentages
- Detailed analysis of unrelated/other/advertisement items
- Source analysis showing which collectors produce problematic items
- Priority score analysis for irrelevant items
- Identification of high-priority false positives
- Word frequency analysis in titles
- Configurable lookback period and customer filtering

**Current Status:**
AI categorization is performing well based on analysis. No immediate action needed.
Monitor for patterns over time and revisit if user feedback indicates issues.

**Future Improvements (if needed):**
- Fine-tune AI prompt based on specific patterns
- Add user feedback mechanism for reporting miscategorizations
- Customer-specific categorization rules
- Category-specific prompt templates

---

#### 24. Configure Per-Source Collection Intervals
**Status:** ✅ Complete
**Effort:** Medium
**Description:** Allow configuration of collection schedule per source type with flexible hour-based intervals.

**Implemented Features:**
- ✅ Time-based interval system (1, 3, 6, 12, 24, 48, 168 hours)
- ✅ Elapsed time checking using CollectionStatus.last_run
- ✅ Single periodic job (runs every hour, checks all sources)
- ✅ Per-source interval configuration in Platform Settings
- ✅ Backward compatible with legacy 'hourly'/'daily' values
- ✅ Comprehensive CollectionStatus tracking for all sources
- ✅ Consolidated UI in Platform Settings → Collection Timing

**Technical Implementation:**
- Changed from collection_type model to elapsed-time checking
- source_intervals stored as numeric hours in platform settings
- Periodic job checks if `hours_elapsed >= configured_interval`
- Manual collections still run all sources immediately
- Debug logging shows elapsed vs interval for each source

**Default Intervals:**
- News API: 1 hour (fast-updating)
- RSS: 1 hour (frequently updated)
- Yahoo Finance News: 1 hour (financial news)
- Twitter: 3 hours (social media)
- Australian News: 6 hours (regional)
- Google News: 6 hours (aggregated)
- Press Releases: 12 hours (official releases)
- Web Scraper: 12 hours (custom sources)
- Reddit: 24 hours (community)
- LinkedIn: 24 hours (rate limited)
- LinkedIn User: 24 hours (heavily rate limited)

---

#### 25. Country Focus Configuration (Per Customer)
**Status:** Pending
**Effort:** Medium
**Description:** Filter news by region/country to reduce noise from irrelevant geographic markets.

**Configuration (per customer):**
```yaml
country_focus:
  primary: "AU"  # Australia
  include_global: true  # Include global news
  exclude_regions: ["US-state", "UK-local"]  # Exclude local regional news
```

**Implementation:**
- Add country/region detection in AI processing
- Filter out news from irrelevant regions
- Boost priority for news from target regions
- UI in Customer Settings

**Use Cases:**
- Australian companies don't need US state news
- US companies may want to exclude APAC regional news
- Global companies want everything

---

#### 26. Daily Summary Schedule Configuration
**Status:** ✅ Complete
**Effort:** Small-Medium
**Description:** Allow users to configure when daily summaries are generated automatically.

**Implemented Features:**
- ✅ Schedule configuration in `daily_briefing.schedule` (enabled, hour, minute)
- ✅ Scheduler job checks settings on startup and schedules accordingly
- ✅ Automatic generation job calls API endpoint for all customers
- ✅ UI toggle in Platform Settings → Daily Briefing tab
- ✅ Hour picker (0-23) with friendly time display
- ✅ Default: disabled, 8:00 AM
- ✅ Clear note about requiring server restart for changes

**Technical Implementation:**
- Backend: `app/api/settings.py` (schedule schema in daily_briefing)
- Backend: `app/scheduler/jobs.py` (generate_daily_summaries function and scheduled job)
- Frontend: `PlatformSettingsModal.jsx` (schedule UI in Daily Briefing tab)
- Scheduler loads settings from database on startup
- Job added to APScheduler with CronTrigger at configured time
- Generates summaries for all customers via `/api/analytics/daily-summary-ai/{customer_id}?force_refresh=true`

**How It Works:**
1. User enables schedule and sets time in Platform Settings
2. On server restart, scheduler reads configuration
3. If enabled, adds daily job at configured time
4. Job runs and generates AI summaries for all customers
5. Summaries cached in database for quick retrieval

---

#### 27. User-Configurable Customer Tab Colors
**Status:** ✅ Complete
**Effort:** Small
**Description:** Allow users to assign colors to customer tabs for visual differentiation and workspace theming.

**Implemented Features:**
- ✅ Added `tab_color` field to Customer model (hex color string)
- ✅ Color picker in Customer Edit Modal with preset palette
- ✅ 9 preset colors (white, yellow, red, orange, green, blue, purple, pink, gray)
- ✅ Custom color picker for any hex color
- ✅ Applied to customer tab button
- ✅ Applied to customer info header background
- ✅ Applied to entire main content area background
- ✅ Default white color for new customers
- ✅ Database migration script provided

**Technical Implementation:**
- Backend: Added `tab_color` column to customers table
- Backend: Updated schemas (CustomerBase, CustomerUpdate, CustomerResponse)
- Frontend: Color picker UI with preset palette and custom hex input
- Frontend: Dynamic styling applied to tab, header, and main-layout
- Alembic migration: `add_customer_tab_color.py`

**Benefits:**
- ✅ Quick visual identification of which customer you're viewing
- ✅ Color-coded workspace for better organization
- ✅ White cards pop nicely from colored backgrounds
- ✅ Better UX with many customers

---

#### 28. Further Smart Feed Tuning
**Status:** Ongoing
**Effort:** Large (ongoing)
**Description:** Continuous optimization of smart feed filtering, priority scoring, and category weighting.

**Areas for Tuning:**
- Priority score thresholds (currently 0.3 min, 0.7 high)
- Category weights and preferences
- Source preference defaults
- Recency boost amount and threshold
- Diversity control parameters
- Min/max items per source

**Process:**
- Monitor user feedback on filtered items
- A/B test different thresholds
- Analyze which items users ignore vs keep
- Adjust based on customer-specific patterns

---

#### 29. YouTube URL to Channel ID Auto-Resolution
**Status:** Pending
**Effort:** Small
**Description:** Allow users to paste full YouTube channel URLs instead of requiring manual channel ID extraction.

**Current Limitation:**
Users must manually find the channel ID (UCxxx...) from YouTube's page source, which is not user-friendly.

**Proposed Enhancement:**
- Accept full YouTube URLs in any format:
  - `youtube.com/@ChannelName` (handle)
  - `youtube.com/c/CustomName` (custom URL)
  - `youtube.com/channel/UCxxx...` (channel ID)
  - `youtube.com/user/Username` (legacy)
- Automatically extract/resolve to channel ID using YouTube Data API
- Store both friendly display name and resolved channel ID
- Show friendly name in UI, use channel ID for API calls

**Implementation:**
- Add URL parsing to extract channel identifier
- Call YouTube Data API to resolve to channel ID
- Add validation and error handling
- Update UI placeholder text to encourage URL pasting

**Benefits:**
- ✅ Significantly improved user experience
- ✅ Removes technical barrier for non-technical users
- ✅ Reduces setup friction
- ✅ Users can copy-paste directly from browser

**Note:** Should be implemented after core YouTube feature is tested in production.

---

#### 29. Email Inbox Monitoring for News Alerts
**Status:** Pending
**Effort:** Medium
**Description:** Monitor dedicated email inbox for news alerts, subscriptions, and notifications from websites that don't offer RSS feeds or APIs.

**Use Cases:**
- **News Alert Subscriptions** - Google Alerts, industry newsletters, company notifications
- **Press Release Services** - PR Newswire, Business Wire email alerts
- **Industry Publications** - Trade publications that only offer email delivery
- **Government Alerts** - Regulatory agencies, government procurement notices
- **Competitor Updates** - Newsletter subscriptions from competitor websites
- **Event Notifications** - Conference announcements, webinar invitations

**Implementation:**

**Email Access Options:**
- **IMAP** - Connect to any standard email inbox (Gmail, Outlook, etc.)
- **Gmail API** - Better integration for Gmail accounts
- **Microsoft Graph API** - Better integration for Outlook/Exchange
- **Dedicated Inbox** - Recommend creating hermes@company.com for collection

**Processing Flow:**
1. Connect to email inbox via IMAP/API
2. Fetch unread emails from configured folders
3. Parse email content (HTML + plain text)
4. Extract article links and content
5. Follow links to fetch full articles when possible
6. Process as intelligence items
7. Mark emails as read or move to processed folder
8. Handle attachments (PDFs, newsletters)

**Email Parsing:**
- **Link Extraction** - Identify article URLs in email body
- **Content Extraction** - Extract text from HTML emails
- **Newsletter Unwrapping** - Parse newsletter formats (Substack, Mailchimp, etc.)
- **PDF Attachments** - Extract text from PDF attachments
- **Signature Removal** - Clean marketing footers and signatures
- **Sender Detection** - Identify source from sender/subject

**Configuration (per customer):**
```yaml
email_monitoring:
  enabled: true
  connection_type: "imap"  # imap, gmail_api, graph_api
  server: "imap.gmail.com"
  port: 993
  username: "hermes@company.com"
  password_env: "EMAIL_PASSWORD"  # Environment variable
  folders: ["INBOX", "News Alerts"]
  mark_as_read: true
  move_to_folder: "Processed"
  check_interval_hours: 1
  process_attachments: true
  attachment_types: ["pdf"]
  sender_whitelist:
    - "alerts-noreply@google.com"
    - "news@businesswire.com"
    - "alerts@company-competitor.com"
```

**Intelligence Item Metadata:**
- Source type: "email"
- Source tier: Varies (tier 2 for press releases, tier 3 for newsletters)
- Email sender and subject stored
- Link to original article when available
- Flag if extracted from attachment

**Security Considerations:**
- Store credentials in environment variables
- Support OAuth2 for Gmail/Outlook (no password storage)
- Encrypted connection (IMAP over SSL)
- Optional: dedicated email account reduces risk
- Email credentials not exposed in UI (masked)

**Technical Details:**
- **Libraries:**
  - Python `imaplib` for IMAP
  - `google-api-python-client` for Gmail API
  - `msal` for Microsoft Graph API
  - `beautifulsoup4` for HTML parsing
  - `PyPDF2` or `pdfplumber` for PDF extraction
- **Rate Limiting:** Email provider limits (Gmail: 2500/day)
- **Collection Interval:** Default 1 hour (configurable)
- **Deduplication:** URL-based dedup with existing items

**UI Configuration:**
- Email settings in Customer Edit Modal or Platform Settings
- Test connection button
- Show last check time and email count
- Display parsing errors (malformed emails)

**Advantages:**
- ✅ Access to sources without APIs or RSS
- ✅ Captures newsletter-exclusive content
- ✅ Works with Google Alerts and other alert services
- ✅ Complements existing collectors
- ✅ Simple setup (just need email credentials)

**Limitations:**
- Requires dedicated email account or folder
- Email format parsing can be complex
- May capture marketing content (needs filtering)
- Some emails are HTML-heavy with little text

**Phased Approach:**
1. **Phase 1** - Basic IMAP connection, link extraction
2. **Phase 2** - HTML email content extraction
3. **Phase 3** - PDF attachment processing
4. **Phase 4** - Gmail/Outlook API for better integration
5. **Phase 5** - Smart newsletter parsing (Substack, etc.)

**Example Workflow:**
1. User subscribes to Google Alerts for "Company Name"
2. Configures Hermes to monitor alerts@company.com
3. Google Alert arrives hourly with 5 new articles
4. Hermes extracts article links
5. Fetches full article content from each link
6. Processes as intelligence items with proper source attribution
7. Marks email as read, moves to "Processed" folder
8. Articles appear in Hermes feed alongside other sources

---

### Completed Quick Improvements (November 2025)

**✅ Session 2025-11-06:**
- ✅ Remove hackernews and github as sources (#18 equivalent)
- ✅ UI Auto Refresh - Configurable polling (1-30 min intervals), manual refresh tracking, localStorage persistence
- ✅ Flag newsroom RSS feeds - Trusted source flag for RSS feeds, press releases, newsrooms (prevents false irrelevant marking)
- ✅ Domain blacklist - Filter out low-quality domains at collection stage with UI configuration
- ✅ Show clustered items in Full Feed mode - Cluster information visible in both feed modes

**Note:** All pending items have been moved to Priority 5 (UX Polish & Optimization) as roadmap items #18-25.

---
## Future Enhancements (Beyond Post-Beta)

### Major Enhancement Projects

#### Product Opportunity Detection & Matching System
**Status:** Future Enhancement (Requires Product Wiki)
**Effort:** Very Large (9-15 months phased)
**Description:** AI-powered system to identify customer pain points from intelligence and match them to your product catalog for account management opportunities.

**Business Value:**
- Proactive opportunity identification for account managers
- Data-driven product recommendations based on actual customer challenges
- Competitive displacement opportunities (customer complains about competitor product)
- Cross-sell and upsell intelligence
- Account health monitoring (identify at-risk accounts with unaddressed needs)

**Prerequisites:**
- **Product Wiki/Database** (Separate Project) - Wiki-style pages for each product/product family
  - Product descriptions and capabilities
  - Pain points addressed
  - Use cases and customer profiles
  - Competitive positioning
  - Integration requirements
  - Typical deal size and sales cycle

**Phase 1: Pain Point Extraction (2-3 months)**
- Add AI processing to extract customer challenges from intelligence
- New `pain_points` field in ProcessedIntelligence table
- Categorization: infrastructure, security, costs, performance, compliance, scalability
- Confidence scoring
- UI display of identified pain points per customer
- Timeline view showing when pain points were mentioned

**Phase 2: Product Wiki Integration (1-2 months)**
- API integration with Product Wiki
- Sync product metadata to Hermes
- Product catalog caching
- Search and browse products within Hermes

**Phase 3: Matching Engine (2-3 months)**
- **Semantic Matching** - Vector embeddings for pain points and products
- **AI Reasoning** - Claude analyzes context and recommends specific solutions
- **Confidence Scoring** - High/Medium/Low confidence matches
- **Contextual Analysis** - Consider customer size, industry, existing infrastructure
- **Multi-product Solutions** - Recommend product bundles when appropriate

**Phase 4: Opportunity Management UI (2 months)**
- **Opportunities Tab** - New section on customer page
- **Opportunity Cards** - Pain point + Recommended product(s) + Reasoning
- **Evidence Timeline** - Show intelligence items that revealed the pain point
- **Opportunity Tracking** - Status workflow (identified → qualified → proposed → won/lost)
- **Suggest Solution** - Generate email/pitch template
- **CRM Integration** - Push opportunities to Salesforce/CRM

**Phase 5: Account Intelligence Dashboard (1 month)**
- Account health scores based on identified pain points
- Cross-sell opportunity matrix
- Competitive displacement alerts
- Upsell timing recommendations
- Team collaboration on opportunities

**Data Model:**
```yaml
pain_points:
  - id: "pp_001"
    customer_id: 123
    category: "infrastructure_scaling"
    description: "Data center costs spiraling out of control"
    confidence: 0.95
    first_mentioned: "2025-11-01"
    last_mentioned: "2025-11-05"
    mention_count: 3
    intelligence_items: [456, 789, 1011]

opportunities:
  - id: "opp_001"
    customer_id: 123
    pain_point_id: "pp_001"
    product_id: "prod_storage_x5000"
    product_family: "Storage Solutions"
    confidence: 0.88
    reasoning: "Customer experiencing high data center costs. X5000 offers 40% cost reduction vs current infrastructure based on typical customer savings."
    status: "identified"
    assigned_to: "account_manager_email"
    created_at: "2025-11-05"
    evidence_items: [456, 789]
```

**API Endpoints:**
- `GET /api/opportunities/{customer_id}` - List opportunities for customer
- `GET /api/pain-points/{customer_id}` - List identified pain points
- `POST /api/opportunities/{opp_id}/status` - Update opportunity status
- `GET /api/products/match` - Match products to pain point (ad-hoc)
- `POST /api/opportunities/generate-pitch` - Generate solution pitch

**Example Workflow:**
1. Intelligence collected: "Acme Corp CTO discusses data center modernization challenges"
2. AI extracts pain point: "Legacy infrastructure, high maintenance costs, scalability limitations"
3. Matching engine finds: "Hyper-Converged Infrastructure Pro" (92% confidence)
4. Opportunity created with reasoning and evidence
5. Account manager reviews, qualifies opportunity
6. Clicks "Generate Pitch" → AI creates customized email referencing specific challenges mentioned
7. Sends to customer, tracks in CRM
8. Updates opportunity status to "proposed"

**Integration Points:**
- **Product Wiki** - Product metadata and capabilities
- **CRM Systems** - Push opportunities, sync account data
- **Email** - Generate and send pitches
- **Analytics** - Track conversion rates, ROI

**Success Metrics:**
- Pain points identified per customer per month
- Opportunity match accuracy (account manager feedback)
- Conversion rate (opportunities → deals)
- Revenue attributed to AI-identified opportunities
- Time saved in opportunity identification

**Future Enhancements:**
- **Competitive Intelligence** - Match pain points to competitor weaknesses
- **Solution Bundles** - Recommend multi-product solutions
- **Win/Loss Analysis** - Learn from opportunity outcomes
- **Predictive Timing** - Identify optimal time to approach based on budget cycles
- **Custom Pitches** - Generate fully customized presentations
- **Multi-Customer Trends** - Identify industry-wide pain points for product development

---

#### Knowledge Graph Integration
**Status:** Future Enhancement (Research Phase)
**Effort:** Very Large (12-18 months phased)
**Description:** Add a knowledge graph layer to Hermes to map relationships between entities (people, companies, technologies) and unlock advanced intelligence capabilities including relationship mapping, temporal pattern discovery, and predictive insights.

**Business Value:**
- Visualize networks of people, companies, and technologies across your customer landscape
- Discover hidden relationships and warm introduction paths
- Identify patterns in technology adoption and partnership formation
- Predict opportunities based on multi-hop reasoning (e.g., "Companies that partner with X typically adopt Technology Y")
- Detect competitive threats through relationship mapping
- Surface contextual intelligence automatically

**Current Foundation:**
Hermes already extracts entities from intelligence items:
```json
{
  "people": ["Satya Nadella", "Andy Jassy"],
  "companies": ["Microsoft", "AWS", "OpenAI"],
  "technologies": ["Claude AI", "Azure OpenAI", "Kubernetes"]
}
```

**What's Missing for Graph:**
1. Explicit relationship extraction (currently unstructured entities)
2. Relationship types and temporal tracking
3. Confidence scoring for relationships
4. Graph storage and query infrastructure

**Use Cases:**

**1. Relationship Mapping**
- People Networks: Track executives, engineers, decision-makers across companies
  - "Who moved from Company A to Company B?"
  - "Which customer executives have connections to our competitors?"
- Company Relationships: Map partnerships, acquisitions, suppliers, competitors
  - Auto-detect when customer partners with competitor
  - Identify warm introduction paths through the network
- Technology Ecosystems: Connect technologies to companies and people
  - "Which customers use similar tech stacks?"
  - "What technologies do successful customers have in common?"

**2. Temporal Pattern Discovery**
- Career Trajectories: Track people movements creating opportunities
  - "Former Company X engineer joins Customer Y → potential technology migration signal"
- Partnership Evolution: Visualize how relationships change over time
  - Early signals of partnerships before official announcements
- Technology Adoption Curves: See what customers adopt before/after competitors

**3. Enhanced Intelligence Context**
When LinkedIn shows "Executive X joins Company Y", automatically surface:
- Their previous companies (from historical data)
- Technologies they've worked with
- People they're connected to at your customers
- Multi-hop reasoning: "Show technologies used by companies that partner with my customer's competitors"

**4. Opportunity Identification**
- Gap Analysis: "Customer uses Tech A and B, competitors all use Tech C → sales opportunity"
- Warm Introductions: "Your contact at Company X worked with their CTO at Company Z"
- Trigger Events: Chain events together (funding → hiring → technology adoption)

**5. Competitive Intelligence Network**
- Influence Mapping: Which companies/people are central to your market?
- Threat Detection: Track competitor movements in customer's ecosystem
- Market Clustering: Discover hidden segments in your customer base

**6. Predictive Insights**
- Pattern Matching: "Companies that hired AI engineers and partnered with Cloud Provider X typically adopt Solution Y within 6 months"
- Risk Signals: Detect weakening relationships (fewer mentions, sentiment shifts)
- Expansion Opportunities: Customers with similar profiles to successful accounts

**Implementation Phases:**

**Phase 1: Enhanced Entity Extraction (3-4 months)**
- Update AI processor to extract explicit relationships:
  ```json
  {
    "entities": [...],
    "relationships": [
      {
        "source": "Microsoft",
        "type": "PARTNERS_WITH",
        "target": "OpenAI",
        "context": "Strategic partnership announced for AI integration",
        "confidence": 0.92,
        "temporal": "2023-01-23"
      }
    ]
  }
  ```
- Relationship types: EMPLOYED_BY, CEO_OF, PARTNERS_WITH, ACQUIRED, COMPETES_WITH, USES_TECHNOLOGY, INVESTED_IN, etc.
- Temporal tracking: when relationships started/ended
- Confidence scoring: how certain are we about each relationship
- Store relationships in database alongside entities

**Phase 2: Graph Database Infrastructure (2-3 months)**

**Option A: Neo4j (Recommended)**
- Purpose-built graph database
- Cypher query language for graph traversals
- Excellent visualization capabilities
- Docker container alongside existing stack

**Option B: PostgreSQL + Apache AGE**
- Graph queries on relational data
- Unified storage (requires PostgreSQL migration)
- Good for hybrid relational+graph workloads

**Option C: NetworkX (Python Library)**
- Lightweight, Python-native
- Good for analysis and algorithms
- In-memory (need persistence strategy)

**Recommendation:** Neo4j for dedicated graph capabilities, runs in Docker alongside SQLite.

**Phase 3: Graph Population & Sync (1-2 months)**
- Backfill graph from existing processed intelligence entities
- Real-time sync: new intelligence → entity extraction → graph update
- Graph schema design:
  - Person nodes (name, roles, LinkedIn, historical employers)
  - Company nodes (name, domain, industry, size)
  - Technology nodes (name, category, vendor)
  - Relationship edges with properties (type, confidence, temporal range, source items)
- Deduplication and entity resolution (John Smith A vs John Smith B)

**Phase 4: Graph Query API (1-2 months)**
- REST endpoints for graph queries:
  - `/api/graph/relationships/{entity_id}` - Get all relationships for entity
  - `/api/graph/path/{entity_a}/{entity_b}` - Find connection paths
  - `/api/graph/network/{customer_id}` - Get customer's ecosystem graph
  - `/api/graph/similar/{entity_id}` - Find similar entities
  - `/api/graph/influence` - Calculate centrality/influence scores
- Cypher query wrapper for complex traversals
- Graph statistics and analytics

**Phase 5: Graph Visualization UI (2-3 months)**
- Interactive network visualization (D3.js, vis.js, or Cytoscape.js)
- Node types with icons and colors (people, companies, technologies)
- Edge types with different line styles
- Zoom, pan, filter, search in graph
- Click nodes to see entity details and intelligence items
- Time slider to see graph evolution
- Layouts: force-directed, hierarchical, circular

**Phase 6: Graph-Powered Intelligence Features (3-4 months)**
- **Contextual Intelligence:** When viewing an item, show related entities and their connections
- **Network Analysis Tab:** New section on customer page with ecosystem visualization
- **Relationship Alerts:** Notify when new significant relationships detected
- **Path Finding:** "How is Customer A connected to Company B?"
- **Influence Rankings:** Who are the most connected people/companies in your market?
- **Community Detection:** Auto-discover market segments and clusters
- **Predictive Patterns:** "Companies with this profile typically..."

**Phase 7: Advanced Analytics (2-3 months)**
- Pattern detection algorithms:
  - Common technology adoption sequences
  - Partnership formation patterns
  - Career trajectory patterns (which companies lead to which)
- Anomaly detection: unusual relationships or changes
- Opportunity scoring based on graph patterns
- Risk assessment from relationship changes
- Recommendation engine: "You should track these entities based on your network"

**Data Model (Graph Schema):**

```cypher
// Nodes
(person:Person {
  id: "p_001",
  name: "Jane Smith",
  linkedin_url: "...",
  current_role: "CFO",
  current_company_id: "c_001"
})

(company:Company {
  id: "c_001",
  name: "Acme Corp",
  domain: "acme.com",
  industry: "Technology",
  size: "1000-5000"
})

(technology:Technology {
  id: "t_001",
  name: "Kubernetes",
  category: "Container Orchestration",
  vendor: "CNCF"
})

// Relationships
(person)-[:EMPLOYED_BY {
  start_date: "2023-01-15",
  end_date: null,
  role: "CFO",
  confidence: 0.95,
  source_items: [123, 456]
}]->(company)

(company)-[:PARTNERS_WITH {
  announced_date: "2023-06-01",
  partnership_type: "Technology Integration",
  confidence: 0.88,
  source_items: [789]
}]->(company2)

(company)-[:USES {
  adopted_date: "2022-03-15",
  use_case: "Production Infrastructure",
  confidence: 0.92,
  source_items: [234, 567]
}]->(technology)

(person)-[:KNOWS {
  confidence: 0.75,
  context: "Both worked at Microsoft",
  source: "inferred"
}]->(person2)
```

**Example Graph Queries:**

```cypher
// Find all executives who moved from competitors to customers
MATCH (competitor:Company)-[:COMPETES_WITH]->(customer:Customer)
MATCH (person:Person)-[r1:EMPLOYED_BY]->(competitor)
MATCH (person)-[r2:EMPLOYED_BY]->(customer)
WHERE r1.end_date < r2.start_date
RETURN person, competitor, customer, r1, r2

// Find shared technologies between customer and competitor
MATCH (customer:Company {id: "cust_123"})-[:USES]->(tech:Technology)<-[:USES]-(competitor:Company)
RETURN tech, competitor
ORDER BY tech.category

// Find warm introduction paths
MATCH path = (myContact:Person)-[:KNOWS*1..3]-(targetExec:Person)
WHERE myContact.id = "p_my_contact"
  AND targetExec.current_company_id = "target_company"
RETURN path, length(path) as degrees
ORDER BY degrees ASC

// Predict technology adoption
MATCH (similar:Company)-[:USES]->(tech:Technology)
WHERE similar.industry = "Finance"
  AND similar.size = "1000-5000"
WITH tech, count(similar) as adopters
WHERE adopters > 5
RETURN tech.name, adopters
ORDER BY adopters DESC
```

**UI Mockups:**

```
┌─ Network Analysis ────────────────────────────────────────┐
│ [🔍 Search] [🎯 Filter] [⏱️ Timeline: All Time ▾]          │
│                                                            │
│  ┌────────────────────────────────────────────────────┐   │
│  │         [Interactive Network Graph]                │   │
│  │                                                     │   │
│  │        (Person) ───EMPLOYED_BY───> (Company)       │   │
│  │           │                           │             │   │
│  │           │                           │             │   │
│  │        KNOWS                     PARTNERS_WITH      │   │
│  │           │                           │             │   │
│  │           ▼                           ▼             │   │
│  │        (Person) <───USES───── (Technology)         │   │
│  │                                                     │   │
│  └────────────────────────────────────────────────────┘   │
│                                                            │
│  Selected: Jane Smith (CFO @ Acme Corp)                   │
│  ├─ Relationships: 15 connections                         │
│  ├─ Current: CFO at Acme Corp (2023-present)              │
│  ├─ Previous: VP Finance at TechCo (2020-2023)            │
│  ├─ Connected to: 3 of your tracked executives            │
│  └─ Technologies: Kubernetes, AWS, Snowflake              │
│                                                            │
│  [View Intelligence Items (23)] [LinkedIn Profile]        │
└────────────────────────────────────────────────────────────┘
```

**Technical Stack:**
- **Graph DB:** Neo4j (Community Edition, Docker container)
- **Graph Driver:** neo4j-python-driver
- **Visualization:** D3.js or vis.js (frontend)
- **Query Layer:** Cypher queries wrapped in Python API
- **Sync Strategy:** Event-driven updates from intelligence processing

**Performance Considerations:**
- Index frequently queried nodes (people, companies)
- Cache common graph queries (customer ecosystems)
- Incremental updates (don't rebuild entire graph)
- Pagination for large result sets
- Background processing for expensive analytics

**Configuration:**
```yaml
knowledge_graph:
  enabled: true
  neo4j_uri: "bolt://localhost:7687"
  neo4j_user: "neo4j"
  neo4j_password_env: "NEO4J_PASSWORD"
  auto_sync: true  # Sync new intelligence to graph
  relationship_confidence_threshold: 0.5  # Only add high-confidence relationships
  entity_deduplication: true
  inference_enabled: true  # Infer relationships (e.g., person A knows person B if worked at same company)
```

**Success Metrics:**
- Relationships extracted per intelligence item
- Graph size (nodes, edges)
- Query response times
- User engagement with graph features
- Opportunities identified through graph patterns
- Accuracy of inferred relationships

**Challenges:**
- Entity disambiguation (same name, different people)
- Relationship confidence and verification
- Graph size and query performance at scale
- Maintaining graph accuracy as data changes
- Privacy considerations (tracking individuals)
- Temporal complexity (relationships change over time)

**Integration Points:**
- **AI Processor:** Extract relationships during intelligence processing
- **Feed UI:** Show entity connections in item cards
- **Search:** Graph-powered semantic search
- **Opportunities (#Product Opportunity Detection):** Use graph for opportunity matching
- **Deep Research (#10):** Include relationship analysis in research reports
- **Entity Discovery (#30):** Discover entities through graph traversal

**Privacy & Ethics:**
- Only track publicly mentioned information
- Respect LinkedIn privacy settings
- Clear documentation on what data is collected
- Ability to exclude specific entities from tracking
- Comply with data protection regulations (GDPR, CCPA)

**Future Enhancements:**
- **Temporal Graph Queries:** "Who worked together in 2020?"
- **Graph ML:** Node embeddings, link prediction
- **Cross-Customer Insights:** Industry-wide relationship graphs
- **External Graph Integration:** Crunchbase, LinkedIn API, Knowledge graphs
- **Relationship Sentiment:** Track how relationships are portrayed (positive/negative)
- **Automated Relationship Verification:** Cross-reference multiple sources
- **Graph Export:** GraphML, GEXF formats for external analysis
- **Real-time Graph Updates:** WebSocket-based live graph visualization

**Example Workflow:**
1. Intelligence collected: "Microsoft announces partnership with OpenAI for Azure AI services"
2. AI extracts entities: Microsoft (Company), OpenAI (Company), Azure (Technology)
3. AI extracts relationship: Microsoft --[PARTNERS_WITH]--> OpenAI (confidence: 0.95)
4. Graph updated with new relationship and timestamp
5. User viewing Microsoft's network sees new OpenAI connection
6. System detects pattern: "3 of your customers use Azure, may be interested in OpenAI integration"
7. Opportunity alert created based on graph pattern
8. Account manager explores graph to find warm introduction path to OpenAI

**Why Build This:**
- Transforms isolated intelligence items into connected knowledge
- Unlocks insights impossible to see from individual items
- Provides competitive advantage through relationship intelligence
- Enables predictive capabilities (pattern-based forecasting)
- Creates network effects (more data → better graph → better insights)
- Unique differentiator for Hermes platform

**Dependencies:**
- Requires stable entity extraction (#current)
- Benefits from Entity Discovery feature (#30)
- Integrates with Deep Research (#10)
- Powers Product Opportunity Detection (Product Wiki feature)

---

### Additional Features to Consider

- **Microsoft Teams Integration** - Similar to Slack integration
- **Export Capabilities** - PDF reports, Excel exports, CSV downloads
- **Advanced Analytics** - Trend detection, topic modeling, sentiment trends over time
- **Multi-user Support** - User accounts, permissions, team collaboration
- **Mobile App** - Native iOS/Android apps
- **Real-time Updates** - WebSocket for live dashboard updates
- **Webhook Support** - Send intelligence to external systems
- **API Rate Limiting** - Protect API from abuse
- **Multi-language Support** - Non-English news sources and AI processing
- **Competitive Intelligence** - Dedicated competitor tracking dashboard
- **Custom AI Models** - Train customer-specific models
- **Integration Hub** - Zapier, IFTTT, n8n integration

### Technical Improvements

- **Diagnostic & Management Tooling** ✅ - Enhanced hermes-diag CLI tool
  - Added LinkedIn management commands (dates, delete posts/profiles)
  - Added vector store rebuild capability
  - Comprehensive documentation in DIAGNOSTICS.md
  - Supports force mode for scripting
  - All tools integrated into single CLI
- **Database Migration to PostgreSQL** - Better performance, full-text search
- **Kubernetes Deployment** - Scalable production deployment
- **Monitoring & Alerting** - Prometheus, Grafana dashboards
- **Automated Testing** - Comprehensive test suite, CI/CD pipeline
- **Performance Optimization** - Caching, query optimization, async processing
- **Security Hardening** - Authentication, encryption, audit logs
- **Backup & Recovery** - Automated backups, disaster recovery plan

---

## Timeline (Proposed)

### Phase 1 (1-2 months) - Data Quality
- Fix stock market data ✅ (#1)
- Implement hybrid search ✅ (#2)
- Add AFR news source (#3)
- Improve Google News results (#4)
- Explore other news sources (#5)
- Add YouTube channel monitoring - transcript-based ✅ (#6)
- Add Podcast episode monitoring - transcript-based (#7)
- Fix Reddit integration ✅ (#8)
- Add email inbox monitoring for news alerts (#29)

### Phase 2 (1-2 months) - Intelligence & UX
- Make daily briefing prompts configurable ✅ (#9)
- Deep research mode (#10)
- Design and implement relevance feedback loop (#11)
- Automatic entity & keyword discovery (#30)
- Improve AI filtering based on feedback
- Add customer-specific learning
- Fix mobile browser layout ✅ (#12)
- Implement story clustering & deduplication ✅ (#13)
- Collection error monitoring & alerts ✅ (#14)
- Build customer management UI ✅ (#15)

### Phase 3 (1 month) - Distribution
- Add email digest (#16)
- Add Slack integration (#17)
- Test and refine notifications

### Phase 4 (2-3 weeks) - UX Polish & Optimization
- Move Australian news config (#18) ✅
- Add tooltips to UI buttons (#19) ✅
- Improve alert clearing behavior (#20) ✅
- Fix items marked as irrelevant (#21) ✅
- Configure per-source collection intervals (#22) ✅
- Country focus configuration (#23)
- Daily summary schedule (#24) ✅
- Customer tab colors (#25) ✅
- Smart feed tuning (#26) - Ongoing

---

## Success Metrics

**Data Collection:**
- \>90% uptime for all data sources
- \<5% failed AI processing rate
- Average 50+ items collected per customer per day

**AI Quality:**
- \>80% of kept items rated as relevant
- \<20% false positive rate (irrelevant items shown)
- Priority scoring accuracy >75%

**User Engagement:**
- Daily active usage
- Email open rate >40%
- Slack click-through rate >30%
- Average time spent on platform

---

**Last Updated:** 2025-11-14
**Version:** Beta → 1.0

---

## Recent Additions (November 2025)

### Session 2025-11-11 ✅
- **URL Deduplication Fix** - Changed from globally unique URLs to per-customer unique (customer_id, url) constraint, allowing same article to be collected for multiple customers
- **Timezone Display Fix** - Added 'Z' suffix to datetime serialization ensuring UTC timestamps display correctly in browser (fixes 11-hour offset issue for Australian timezone)
- **ANZ Keyword Expansion** - Expanded from 7 to 24 keywords including industry terms, comparative terms, executive names, and common patterns
- **Migration Scripts** - Created database migration for URL uniqueness and verification scripts for both database schema and timezone handling

### Session 2025-11-06 ✅
- **UI Auto-Refresh** - Configurable automatic feed polling with intervals from 1-30 minutes, visual indicators, and localStorage persistence
- **Trusted Source Flags** - RSS feeds, press releases, and newsrooms can be flagged as trusted to prevent false "irrelevant" categorization
- **Domain Blacklist** - Filter out low-quality domains (yahoo.com, msn.com, etc.) at collection stage with UI configuration
- **Full Feed Clustering** - Show cluster information and expandable related items in Full Feed mode
- **Remove Unused Sources** - Cleaned up HackerNews and GitHub collectors (~500+ lines removed)
- **YouTube & Podcast Collectors** - Updated to transcript-based approach (simpler, faster, no audio processing needed)

### Session 2025-11-07 ✅
- **Per-Source Collection Intervals (#22)** - Flexible hour-based intervals (1-168 hours), time-elapsed checking, single periodic job, consolidated UI
- **Customer Tab Colors (#25)** - Color picker with preset palette, colors applied to entire workspace area for visual organization
- **Australian News Configuration (#18)** - Moved from hardcoded/YAML to Platform Settings with full CRUD UI for managing news sources
- **Daily Summary Scheduling (#24)** - Automatic daily summary generation at configurable time with scheduler integration
- **Alert Clearing Behavior (#20)** - Improved dismissal with persistent state across refreshes
- **AI Categorization Analysis (#21)** - Created analysis script to review items marked as irrelevant/other; confirmed AI performing well
- **YouTube Transcript Collector (#6)** - Full implementation with YouTube Data API v3, transcript fetching, channel monitoring, keyword search
- **Deep Research Mode (#10)** - Added comprehensive roadmap entry for AI-powered deep research tool with multi-step agents, report generation
- **Product Opportunity Detection** - Added major enhancement for pain point extraction and product matching system (requires Product Wiki)
- **YouTube & Podcast Roadmap** - Updated to transcript-based approach (simpler, no audio processing)
- **Tooltips (#19)** - Marked as complete (already implemented with HTML title attributes)
- **Error Handling Improvements** - Better Reddit authentication errors, disabled ChromaDB telemetry spam, suppressed tokenizers warnings
- **UI Consistency** - Made both gear icons use same styling with blue hover effect
- **Bug Fixes** - Fixed SessionLocal imports in scheduler jobs and analysis tools

### Parallel Collection Architecture ✅
- Implemented concurrent customer collection (4 workers)
- Global rate limiter coordination across all sources
- Incremental LinkedIn processing (items visible immediately)
- 3x performance improvement (45 min → 5-6 min for 3 customers)

### Session 2025-11-14 ✅
- **Email Inbox Monitoring (#29)** - Added roadmap item for monitoring email inboxes (Google Alerts, newsletters, press release alerts) via IMAP/Gmail API/Graph API
- **Automatic Entity & Keyword Discovery (#30)** - Added roadmap item for AI-powered discovery of new people, companies, keywords, and products from intelligence to automatically suggest additions to monitoring configuration
