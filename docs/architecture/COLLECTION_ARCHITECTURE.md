# Collection Architecture

## Overview

Hermes uses a parallel collection architecture with global rate limiting to efficiently gather intelligence from multiple sources while respecting API limits and avoiding detection.

## Architecture Components

### 1. Global Rate Limiter

**File:** `backend/app/utils/rate_limiter.py`

Coordinates rate limits across all sources and customers using a sliding window algorithm.

**Per-Source Limits:**
- LinkedIn: 10 requests/min (conservative for scraping)
- Reddit: 60 requests/min
- News API: 100 requests/min
- GitHub: 60 requests/min
- Twitter: 60 requests/min

**How it works:**
```python
rate_limiter = GlobalRateLimiter()
await rate_limiter.acquire('linkedin')  # Blocks if rate limit reached
# ... make request ...
```

**Features:**
- Sliding window rate limiting
- Thread-safe async/await support
- Real-time statistics and monitoring
- Configurable limits per source type

### 2. Task Queue & Worker Pool

**File:** `backend/app/utils/rate_limiter.py`

Enables concurrent collection across multiple customers.

**Features:**
- Configurable worker count (default: 4)
- Automatic error handling
- Result aggregation
- Clean start/stop lifecycle

**Worker Allocation:**
- Single customer collection: 1 worker
- All customers collection: 4 workers (parallel)

**Usage:**
```python
queue = TaskQueue(max_concurrent=4)
await queue.start_workers()
await queue.add_task(collect_customer, customer_id)
await queue.wait_completion()
```

### 3. Parallel Collection Orchestration

**File:** `backend/app/scheduler/collection.py`

Coordinates parallel execution across multiple customers with proper error handling.

**Features:**
- Separate DB sessions per worker (thread-safe)
- Rate limiter statistics logging
- Error aggregation across all workers
- Incremental processing support

### 4. Collection Scheduler

**File:** `backend/app/scheduler/jobs.py`

APScheduler-based job scheduling for automated collections.

**Jobs:**
- **Periodic Collection** - Hourly job that checks which sources need collection based on elapsed time
- **Daily Purge** - Midnight job to remove old intelligence items
- **Daily Summary** - Configurable time for AI-generated executive summaries

**Day-of-Week Selection:**
- Collection engine: Configurable days (default: all 7 days)
- Summary generation: Configurable days (default: Mon-Fri)

## Performance Improvements

### Before Parallel Collection

**Sequential Processing:**
- 3 customers × 15 min each = **45 minutes total**
- Items appear only after ALL collections complete
- New event loop per customer (inefficient)
- No cross-customer rate limiting

### After Parallel Collection

**Concurrent Processing:**
- 3 customers = **~5-6 minutes total** (87% faster)
- Items appear incrementally as they're collected
- Single event loop with worker pool
- Up to 4 customers collected concurrently
- Global rate limiter prevents API abuse

## LinkedIn Scraping Strategy

### The "Low and Slow" Philosophy

> **"Scraping LinkedIn over 1 hour is perfectly acceptable. Slow and invisible is better than fast and blocked."**

For web scraping (LinkedIn, Twitter, etc.), speed is NOT the goal - **reliability and invisibility** are.

### Rate Limiting Layers

LinkedIn collection has **3 layers** of protection:

**Layer 1: Per-Collector Rate Limiter**
```python
rate_limit=5  # 5 profiles per minute max
```

**Layer 2: Randomized Within-Customer Delays**
```python
3-6 seconds between profiles (random)
2-5 seconds for page loads (random)
```

**Layer 3: Global Between-Customer Delays**
```python
60-120 seconds between profiles (conservative strategy)
300-600 seconds between customers (5-10 minutes)
```

### Scraping Strategies

Three preset strategies configurable via platform settings:

#### Conservative (Production Default)
```
Delays:
- Between profiles: 60-120 seconds (1-2 minutes)
- Between customers: 300-600 seconds (5-10 minutes)

Total time: ~1 hour per customer
Risk level: ⭐ Very Low
Detection: Looks completely human
```

#### Moderate
```
Delays:
- Between profiles: 30-60 seconds
- Between customers: 120-240 seconds (2-4 minutes)

Total time: ~30 minutes per customer
Risk level: ⭐⭐ Low
```

#### Aggressive (Use with caution)
```
Delays:
- Between profiles: 3-6 seconds
- Between customers: 10-15 seconds

Total time: ~15 minutes per customer
Risk level: ⭐⭐⭐ Medium-High
```

### Configuration

Database-driven via `platform_settings` table:

```json
{
  "collector_config": {
    "linkedin": {
      "scraping_strategy": "conservative",
      "delay_between_profiles_min": 60.0,
      "delay_between_profiles_max": 120.0,
      "delay_between_customers_min": 300.0,
      "delay_between_customers_max": 600.0
    }
  }
}
```

### Why "Low and Slow" Works

1. **Mimics Human Behavior**
   - Matches real human reading speed (30-90 seconds per profile)
   - Randomized delays (no detectable pattern)
   - Browser automation with real user agent

2. **Stays Under Rate Limits**
   - LinkedIn threshold: ~10-20 requests/minute
   - Our conservative rate: ~0.5 requests/minute (20x under threshold)
   - Randomized timing makes detection harder

3. **Spreads Load Over Time**
   - Traditional: Burst of 15 requests in 2 minutes → BLOCKED
   - Low and slow: 1 request every 2 minutes → Never blocked

### Collection Schedule Optimization

**Hourly Collection (00:00):**
- Light collections (news, RSS)
- Skip scraping collectors

**Daily Collection (02:00 AM):**
- Include scraping collectors
- Conservative strategy
- Low LinkedIn usage time
- Expected duration: 2-3 hours for 10 customers

### Anti-Detection Measures

- ✅ Randomized delays between profiles
- ✅ Customer delays between collections
- ✅ Session persistence (shared across customers)
- ✅ Realistic user agent
- ✅ Browser automation (Playwright)
- ✅ No predictable patterns

## Incremental Processing

**File:** `backend/app/collectors/linkedin_playwright_collector.py`

Items are saved and visible in UI immediately after each profile is collected.

**Benefits:**
- Real-time feedback during collection
- No waiting for entire collection to complete
- Better user experience
- Items searchable immediately

**Implementation:**
- Callback-based architecture
- Process items after each profile
- Commit to database incrementally

## Per-Source Collection Intervals

**File:** `backend/app/scheduler/collection.py`

Each source type has a configurable collection interval (1-168 hours).

**How it works:**
1. Periodic job runs every hour
2. Checks each source's last collection time
3. Compares elapsed time vs configured interval
4. Collects if interval has passed

**Default Intervals:**
- News API: 1 hour (fast-updating)
- RSS: 1 hour (frequently updated)
- Yahoo Finance News: 1 hour (financial news)
- Twitter: 3 hours (social media)
- Australian News: 6 hours (regional)
- Google News: 6 hours (aggregated)
- Press Releases: 12 hours (official releases)
- Web Scraper: 12 hours (custom sources)
- YouTube: 12 hours (video content)
- Reddit: 24 hours (community)
- LinkedIn: 24 hours (rate limited)

**Configuration:**
Set in Platform Settings → Collection & Retention → Collection Timing

## Database Schema

### CollectionStatus Table

Tracks collection health per customer and source:

```sql
CREATE TABLE collection_status (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    source_type VARCHAR(50) NOT NULL,
    status VARCHAR(20),  -- 'success', 'error', 'auth_required'
    last_run TIMESTAMP,
    last_success TIMESTAMP,
    error_message TEXT,
    error_count INTEGER,
    UNIQUE(customer_id, source_type)
);
```

**Purpose:**
- Monitor collection health
- Track authentication issues
- Display error banners in UI
- Identify failing collectors

## Error Handling

### Collection Errors

**Error Banner System:**
- Yellow banner for `auth_required` (e.g., LinkedIn logout)
- Red banner for general errors
- Shows source type, error message, and error count
- Dismissible with animation
- Auto-fetches on UI component mount

**API Endpoint:**
```
GET /api/feed/collection-errors
```

Returns active errors for display in UI.

### Rate Limit Handling

**When rate limit is reached:**
1. Worker waits until rate limit window expires
2. Continues collection without failing
3. Logs rate limit statistics
4. No user intervention required

**Rate limit exceeded response:**
```python
await rate_limiter.acquire('linkedin')  # Blocks and waits
```

## Monitoring & Debugging

### Log Output (Conservative Strategy)

```
02:00:00 Starting LinkedIn collection for Customer: Acme Corp
02:00:02 Collecting profile: John Smith (CEO)
02:01:47 [WAIT 105 seconds] Next profile...
02:01:47 Collecting profile: Jane Doe (CTO)
02:03:52 [WAIT 125 seconds] Next profile...
02:05:44 LinkedIn collection complete for Customer: Acme Corp
02:05:44 ⏰ Waiting 472 seconds (7.9 min) before next customer...
```

### Success Indicators

- ✅ All profiles collected
- ✅ No "authwall" or "rate limit" errors
- ✅ Even distribution of requests
- ✅ Collection status: success for all customers

### Rate Limiter Statistics

Logged after each collection:

```
INFO - Rate limiter statistics:
  linkedin: 15/10 requests (150% utilization)
  reddit: 45/60 requests (75% utilization)
  news: 89/100 requests (89% utilization)
```

## Implementation Timeline

### November 2, 2025
- ✅ Randomized delays between profiles (configurable)
- ✅ Customer delays between collections (configurable)
- ✅ Session persistence (shared across customers)
- ✅ Anti-detection measures

### November 3, 2025
- ✅ Parallel collection architecture (4 workers)
- ✅ Global rate limiter coordination
- ✅ Incremental LinkedIn processing
- ✅ Task queue system
- ✅ 3x performance improvement

### November 6-8, 2025
- ✅ Per-source collection intervals
- ✅ Day-of-week scheduling for collections
- ✅ Day-of-week scheduling for summaries
- ✅ Collection error monitoring UI

## Trade-offs

### Conservative Strategy

**Pros:**
- ✅ Near-zero rate limit risk
- ✅ Looks completely human
- ✅ Sustainable long-term
- ✅ Works with free LinkedIn account
- ✅ No IP blocking

**Cons:**
- ❌ Slower (1 hour per customer vs 2 minutes)
- ❌ Collection job runs longer (okay for scheduled jobs)

### Parallel Collection

**Pros:**
- ✅ 3x faster overall collection time
- ✅ Real-time item visibility
- ✅ Efficient use of I/O-bound waiting
- ✅ Scalable to many customers

**Cons:**
- ❌ More complex architecture
- ❌ Requires careful rate limit coordination

## Future Enhancements

### Short-term
- [ ] UI controls for worker count configuration
- [ ] Auto-tune delays based on error rate
- [ ] Time-of-day optimization

### Medium-term
- [ ] Auto-scale worker count based on customer count
- [ ] Real-time progress indicators in UI
- [ ] Per-source concurrency limits (e.g., max 2 LinkedIn collections at once)

### Long-term
- [ ] Migrate to Celery + Redis if volume increases significantly (>20 customers)
- [ ] Distributed workers across multiple machines
- [ ] Priority-based task queue

## Related Files

**Core Architecture:**
- `backend/app/utils/rate_limiter.py` - GlobalRateLimiter & TaskQueue
- `backend/app/scheduler/collection.py` - Parallel execution logic
- `backend/app/scheduler/jobs.py` - APScheduler job definitions

**Collectors:**
- `backend/app/collectors/base.py` - Base collector with rate limiting
- `backend/app/collectors/linkedin_playwright_collector.py` - LinkedIn scraping
- All other collectors in `backend/app/collectors/`

**Database:**
- `backend/app/models/database.py` - CollectionStatus model
- `backend/app/api/feed.py` - Collection error API endpoint

**Frontend:**
- `frontend/src/components/ErrorBanner.jsx` - Error display
- `frontend/src/components/PlatformSettingsModal.jsx` - Configuration UI

---

**Last Updated:** November 8, 2025
**Status:** Production-ready
**Performance:** 3x faster collection with parallel execution
**Reliability:** Near-zero rate limiting issues with conservative strategy
