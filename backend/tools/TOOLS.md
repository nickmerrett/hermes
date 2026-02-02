# Backend Tools Documentation

This directory contains utility scripts for debugging, diagnostics, data maintenance, and migrations.

All tools should be run from the `backend` directory:
```bash
cd backend
python tools/<script_name>.py [options]
```

---

## Embedding & Vector Store Tools

### regenerate_embeddings.py
**Purpose:** Regenerate embeddings in ChromaDB for specific items or all items.

**When to use:**
- Embeddings are corrupted or mismatched
- After changing the embedding model
- To fix stale embeddings from the old `add()` vs `upsert()` bug

**Usage:**
```bash
# Regenerate all embeddings (can take a while)
python tools/regenerate_embeddings.py --all

# Regenerate items from last N hours
python tools/regenerate_embeddings.py --hours 48

# Regenerate specific item IDs
python tools/regenerate_embeddings.py --ids 4651 4650 4639

# Custom batch size
python tools/regenerate_embeddings.py --all --batch-size 50
```

---

### rebuild_vector_store.py
**Purpose:** Complete vector store reconstruction - resets ChromaDB and rebuilds from scratch.

**When to use:**
- Need to change the distance metric
- Vector store is severely corrupted
- Starting fresh after major changes

**Usage:**
```bash
python tools/rebuild_vector_store.py
```

**Note:** This is more destructive than `regenerate_embeddings.py` - it deletes and recreates the entire collection.

---

### diagnose_embeddings.py
**Purpose:** Verify stored embeddings match what would be generated fresh.

**When to use:**
- Debugging clustering issues
- Suspecting embedding corruption
- Verifying embeddings after regeneration

**Usage:**
```bash
# Check default test IDs
python tools/diagnose_embeddings.py

# Check specific items
python tools/diagnose_embeddings.py 4651 4650 4639
```

**Output:** Shows stored vs fresh embedding similarity. Values < 0.99 indicate a mismatch.

---

### compare_stored_content.py
**Purpose:** Compare documents stored in ChromaDB with current database content.

**When to use:**
- Debugging embedding mismatches
- Verifying ChromaDB contains correct content
- Investigating clustering anomalies

**Usage:**
```bash
# Check default test IDs
python tools/compare_stored_content.py

# Check specific items
python tools/compare_stored_content.py 4651 4650 4639
```

**Output:** Shows if ChromaDB document matches expected `title + content` from database.

---

## Clustering Tools

### debug_clustering.py
**Purpose:** Interactive debugging for story clustering issues.

**When to use:**
- Items not clustering when they should
- Items clustering when they shouldn't
- Understanding why specific items were/weren't clustered

**Usage:**
```bash
# Search for items by keyword
python tools/debug_clustering.py "Rio Tinto"

# Show N most recent items (default: 10)
python tools/debug_clustering.py -n 20

# Combine search with limit
python tools/debug_clustering.py "mining" -n 15
```

**Output includes:**
- Current clustering settings (thresholds, time windows)
- Items with their cluster status and embedding status
- Pairwise similarity analysis (embedding + title similarity)
- Time window analysis
- Overall clustering statistics

---

## Smart Feed Tools

### reset_smart_feed_settings.py
**Purpose:** Delete smart feed config to force reload with new defaults.

**When to use:**
- After schema changes to smart feed settings
- To reset to default configuration

**Usage:**
```bash
python tools/reset_smart_feed_settings.py
```

---

### debug_smart_feed_config.py
**Purpose:** Debug smart feed configuration issues.

---

### diagnose_smart_feed_simple.py
**Purpose:** Simple diagnostic for smart feed issues.

---

### test_smart_feed_api.py
**Purpose:** Test smart feed API endpoints.

---

### test_smart_feed_scenarios.py
**Purpose:** Test various smart feed scenarios.

---

### migrate_smart_feed_settings.py
**Purpose:** Migrate smart feed settings to new schema.

---

## Data Analysis Tools

### analyze_irrelevant_items.py
**Purpose:** Analyze items marked as 'unrelated', 'other', or 'advertisement' to identify AI categorization issues.

**When to use:**
- High percentage of items being marked irrelevant
- Investigating AI categorization accuracy
- Identifying false positives

**Usage:**
```bash
# Analyze last 30 days (default)
python tools/analyze_irrelevant_items.py

# Custom time period
python tools/analyze_irrelevant_items.py --days 7

# Limit items displayed per category
python tools/analyze_irrelevant_items.py --limit 20

# Filter to specific customer
python tools/analyze_irrelevant_items.py --customer-id 1

# Combined options
python tools/analyze_irrelevant_items.py --days 14 --limit 30 --customer-id 2
```

**Output includes:**
- Category distribution with percentages
- Source analysis for problematic items
- Priority score analysis
- Sample items with full details
- Common keywords in problematic titles

---

## LinkedIn Tools

### delete_linkedin_posts.py
**Purpose:** Delete all LinkedIn posts from the database.

**When to use:**
- Clearing out old LinkedIn data
- Resetting LinkedIn collection

**Usage:**
```bash
python tools/delete_linkedin_posts.py
```

---

### delete_linkedin_profiles.py
**Purpose:** Delete LinkedIn profile sources from the database.

---

### check_linkedin_dates.py
**Purpose:** Check and debug LinkedIn post date parsing.

---

## Web Scraping Tools

### debug_selectors.py
**Purpose:** Find correct CSS selectors for Yahoo Finance (or other sites) using Playwright.

**When to use:**
- Yahoo Finance changed their HTML structure
- Debugging scraper selector issues
- Finding new selectors for publisher/date elements

**Usage:**
```bash
python tools/debug_selectors.py
```

**Note:** Requires Playwright (`playwright install chromium`).

---

## Migration Tools

### migrate_ai_processing_fields.py
**Purpose:** Migrate AI processing fields to new schema.

---

### migrate_collection_status.py
**Purpose:** Migrate collection status fields.

---

### verify_collection_status.py
**Purpose:** Verify collection status migration was successful.

---

### migrate_stock_to_yahoo_finance_news.py
**Purpose:** Migrate stock sources to Yahoo Finance news format.

---

### add_platform_settings.py
**Purpose:** Add platform settings to database.

---

## Testing Tools

### test_youtube_transcript.py
**Purpose:** Test YouTube transcript extraction.

---

## Common Patterns

### Running from backend directory
All tools expect to be run from the `backend` directory:
```bash
cd /path/to/hermes/backend
python tools/some_tool.py
```

### Database access
Most tools use `SessionLocal()` from `app.core.database` and handle cleanup:
```python
db = SessionLocal()
try:
    # ... do work
finally:
    db.close()
```

### Progress reporting
Long-running tools report progress every 50 items:
```
Progress: 50/1000 (50 success, 0 errors)
Progress: 100/1000 (100 success, 0 errors)
```
