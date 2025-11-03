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

#### 6. Fix and Test Reddit Data Source
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

#### 7. Platform Settings Configuration (Expanded from Daily Briefing Prompts)
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

#### 8. Design Relevance Feedback Loop
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

#### 9. Fix Mobile Browser Layout
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

#### 10. Implement Story Clustering & Intelligent Deduplication
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

#### 11. Collection Error Monitoring & Alert System
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

#### 12. Customer Management in UI
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

#### 13. Add Email Digest Output
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

#### 14. Add Slack Notification Integration
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
### 15. Move Australian News Sources Configuration into the platofrm modal, rename primary

---

### Bugs ###
Config what sources are collected hourly, what sources are daily or config for each sources interval and behaviour
UI Auto Refresh 
Clearing Alerts behaviour
fixing being marked as irrelevant
adding tooltips to buttons
country focus configuration (per customer)
daily summary schedule

---
## Future Enhancements (Beyond Post-Beta)

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
- Fix Reddit integration ✅ (#6)

### Phase 2 (1-2 months) - Intelligence & UX
- Make daily briefing prompts configurable (#7)
- Design and implement relevance feedback loop (#8)
- Improve AI filtering based on feedback
- Add customer-specific learning
- Fix mobile browser layout ✅ (#9)
- Implement story clustering & deduplication ✅ (#10)
- Collection error monitoring & alerts ✅ (#11)
- Build customer management UI (#12)

### Phase 3 (1 month) - Distribution
- Add email digest (#13)
- Add Slack integration (#14)
- Test and refine notifications

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

**Last Updated:** 2025-11-03
**Version:** Beta → 1.0

---

## Recent Additions (November 2025)

### Parallel Collection Architecture ✅
- Implemented concurrent customer collection (4 workers)
- Global rate limiter coordination across all sources
- Incremental LinkedIn processing (items visible immediately)
- 3x performance improvement (45 min → 5-6 min for 3 customers)
