# Hermes Development Roadmap

## Current Status: Beta Release

Hermes is production-ready for internal use with core features fully functional.

## Post-Beta Enhancement Roadmap

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

#### 8. Fix and Test Reddit Data Source
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

#### 9. Platform Settings Configuration (Expanded from Daily Briefing Prompts)
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

#### 10. Deep Research Mode
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

#### 11. Design Relevance Feedback Loop
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

### Priority 3: User Experience

#### 12. Fix Mobile Browser Layout
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

#### 13. Implement Story Clustering & Intelligent Deduplication
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

#### 14. Collection Error Monitoring & Alert System
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

#### 15. Customer Management in UI
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

#### 16. Add Email Digest Output
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

#### 17. Add Slack Notification Integration
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

#### 18. Move Australian News Sources Configuration into Platform Settings
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

#### 19. Add Tooltips to UI Buttons
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

#### 20. Improve Alert Clearing/Dismissing Behavior
**Status:** ✅ Complete
**Effort:** Small
**Description:** Better error banner dismissal with "dismiss all" option and persistent dismissals.

**Implemented Features:**
- ✅ Error banners can be dismissed
- ✅ Dismissals persist across page refreshes
- ✅ Clear UX for dismissing alerts
- ✅ Improved error banner behavior

---

#### 21. Fix Items Being Marked as Irrelevant
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

#### 22. Configure Per-Source Collection Intervals
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

#### 23. Country Focus Configuration (Per Customer)
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

#### 24. Daily Summary Schedule Configuration
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

#### 25. User-Configurable Customer Tab Colors
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

#### 26. Further Smart Feed Tuning
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

#### 27. YouTube URL to Channel ID Auto-Resolution
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

### Phase 2 (1-2 months) - Intelligence & UX
- Make daily briefing prompts configurable ✅ (#9)
- Deep research mode (#10)
- Design and implement relevance feedback loop (#11)
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

**Last Updated:** 2025-11-07
**Version:** Beta → 1.0

---

## Recent Additions (November 2025)

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
