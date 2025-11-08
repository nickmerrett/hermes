# Hermes Diagnostics CLI

A unified diagnostic tool for debugging and monitoring the Hermes intelligence platform.

## Quick Start

```bash
./hermes-diag --help          # Show all available commands
./hermes-diag all             # Run all diagnostics
./hermes-diag --debug sources # Run with SQL query logging (debug mode)
```

## Debug Mode

By default, `hermes-diag` suppresses SQLAlchemy query logging for clean output. Use the `--debug` flag to see all SQL queries:

```bash
./hermes-diag --debug sources      # Show SQL queries
./hermes-diag --debug all          # Full diagnostics with SQL logging
```

## Available Commands

### 1. `sources` - Collection Statistics

Shows what sources have collected items and their statistics.

```bash
./hermes-diag sources
```

**Output:**
- Total items in database
- Items breakdown by source type (reddit, google_news, rss, etc.)
- Items breakdown by customer
- Recent items (last 24 hours)
- Clustering statistics (multi-source stories, single-source stories)

**Use cases:**
- Verify data collection is working
- Check if a specific source (e.g., Reddit) has collected items
- Monitor collection activity

---

### 2. `config` - Customer Configuration

Check what collection settings are stored in the database for each customer.

```bash
./hermes-diag config
```

**Output:**
- All customers in database
- Collection settings for each (news_enabled, reddit_enabled, etc.)
- Reddit-specific config (subreddits, enabled status)

**Use cases:**
- Verify YAML config has synced to database
- Check if Reddit is enabled for a customer
- Debug why a source isn't collecting

---

### 3. `reddit` - Reddit Items & Clustering

Check Reddit items and their clustering status.

```bash
./hermes-diag reddit
```

**Output:**
- Total Reddit items
- Clustering statistics (primary vs non-primary)
- Detailed info for each Reddit item (cluster_id, is_primary, subreddit)

**Use cases:**
- Verify Reddit collection is working
- Check if Reddit items are being clustered correctly
- See which subreddits items are coming from

---

### 4. `reddit-processed` - Reddit AI Processing

Check if Reddit items have been processed by AI and their categories.

```bash
./hermes-diag reddit-processed
```

**Output:**
- Processing status for each Reddit item
- AI categories assigned (challenge, competitor, unrelated, etc.)
- Sentiment and priority scores
- Items filtered out as 'unrelated'

**Use cases:**
- Debug why Reddit items aren't showing in UI
- Check if items are being categorized as 'unrelated'
- Verify AI processing is working

---

### 5. `api-feed` - Test API Feed Endpoint

Simulates the frontend's API query to show what would be returned.

```bash
./hermes-diag api-feed                # Test default customer
./hermes-diag api-feed "ANZ Bank"     # Test specific customer
./hermes-diag api-feed IBM            # Partial name match works
```

**Output:**
- Smart Feed results (clustered=True, only primaries)
- Full Feed results (clustered=False, all items)
- Reddit items in each feed
- Demonstrates frontend 'unrelated' filter

**Use cases:**
- Debug why items aren't appearing in UI
- Verify API is returning correct items
- Understand Smart Feed vs Full Feed filtering

---

### 6. `sync-config` - Force Config Sync

Force sync customer configuration from YAML to database.

```bash
./hermes-diag sync-config
```

**Output:**
- Sync confirmation
- Updated configuration for each customer
- Reddit enabled/disabled status

**Use cases:**
- After editing config/customers.yaml
- When database config is out of sync
- Before triggering a new collection

**Note:** Config sync happens automatically during collection, but this forces it manually.

---

### 7. `backfill-clustering` - Recluster Items

Cluster all unclustered items in the database using vector similarity.

```bash
./hermes-diag backfill-clustering         # With confirmation prompt
./hermes-diag backfill-clustering --force # Skip confirmation
```

**Output:**
- Progress updates (every 20 items)
- Clustering statistics (new clusters vs joined clusters)
- Performance metrics (items/second)
- Example multi-source stories

**Use cases:**
- After importing historical data
- After changing clustering similarity threshold
- When items were collected but not clustered
- To fix clustering after data issues

**Note:** This can take time with large datasets (~0.2s per item). Use `--force` to skip the confirmation prompt.

---

### 8. `linkedin-dates` - Check LinkedIn Post Dates

Check LinkedIn post dates and age to verify collection timestamps.

```bash
./hermes-diag linkedin-dates
```

**Output:**
- 10 most recent LinkedIn posts
- Published date and collection date
- Age calculation (days and hours)
- Post author information

**Use cases:**
- Verify LinkedIn collection is working
- Check if posts are recent or old
- Debug timestamp issues with LinkedIn data
- Confirm post metadata is correct

---

### 9. `rebuild-vectors` - Rebuild Vector Store

Rebuild the entire vector store from scratch by re-embedding all items.

```bash
./hermes-diag rebuild-vectors         # With confirmation prompt
./hermes-diag rebuild-vectors --force # Skip confirmation
```

**Output:**
- Current and target vector counts
- Progress updates (every 100 items)
- Performance metrics (items/second)
- Search verification test

**Use cases:**
- After ChromaDB corruption or errors
- When embeddings are out of sync with database
- After changing embedding model
- When vector search returns incorrect results

**Warning:** This deletes all existing embeddings and recreates them. Takes approximately 0.5 seconds per item.

---

### 10. `delete-linkedin-posts` - Delete All LinkedIn Posts

**⚠️ DESTRUCTIVE OPERATION** - Delete ALL LinkedIn posts from the database.

```bash
./hermes-diag delete-linkedin-posts         # With confirmation prompt
./hermes-diag delete-linkedin-posts --force # Skip confirmation (DANGEROUS)
```

**Output:**
- Count of LinkedIn posts to delete
- Strong warning message
- Confirmation of deletion

**Use cases:**
- Clear out all LinkedIn data for fresh collection
- Remove corrupted LinkedIn posts
- Reset LinkedIn data during development

**Warning:** This permanently deletes ALL LinkedIn posts. Cannot be undone. Requires typing 'DELETE' to confirm.

---

### 11. `delete-linkedin-profiles` - Delete LinkedIn Profile Items

**⚠️ DESTRUCTIVE OPERATION** - Delete LinkedIn profile items (not regular posts).

```bash
./hermes-diag delete-linkedin-profiles         # With confirmation prompt
./hermes-diag delete-linkedin-profiles --force # Skip confirmation (DANGEROUS)
```

**Output:**
- Count of LinkedIn profile items to delete
- Total LinkedIn posts count
- Remaining posts after deletion
- Strong warning message

**Use cases:**
- Remove profile items that clutter the feed
- Keep only actual LinkedIn posts
- Clean up profile collection artifacts

**Warning:** This permanently deletes profile items. Cannot be undone. Requires typing 'DELETE' to confirm.

---

### 12. `all` - Run All Diagnostics

Run all diagnostic commands in sequence.

```bash
./hermes-diag all
```

**Output:**
- Complete diagnostic suite
- All checks from commands 1-6

**Use cases:**
- Full system health check
- After making changes to config
- Before debugging a specific issue

---

## Common Debugging Scenarios

### Reddit items not showing in UI

```bash
# 1. Check if Reddit is enabled in config
./hermes-diag config

# 2. Check if Reddit items exist in database
./hermes-diag reddit

# 3. Check if items are processed and categorized correctly
./hermes-diag reddit-processed

# 4. Check what API would return to frontend
./hermes-diag api-feed "ANZ Bank"
```

### Config changes not taking effect

```bash
# 1. Force sync config from YAML to database
./hermes-diag sync-config

# 2. Verify config was synced
./hermes-diag config

# 3. Trigger a collection
curl -X POST http://localhost:8000/api/jobs/trigger
```

### No items collected from a source

```bash
# 1. Check collection statistics
./hermes-diag sources

# 2. Check customer config
./hermes-diag config

# 3. Check backend logs
# (Look for collector errors)
```

### Items missing from Smart Feed

```bash
# 1. Test what API returns
./hermes-diag api-feed

# 2. Check if items are marked as primary
./hermes-diag reddit  # or appropriate source

# 3. Check if items are categorized as 'unrelated'
./hermes-diag reddit-processed
```

### LinkedIn collection issues

```bash
# 1. Check if LinkedIn posts exist and their age
./hermes-diag linkedin-dates

# 2. Check collection statistics
./hermes-diag sources

# 3. Delete old/corrupted data and recollect
./hermes-diag delete-linkedin-posts  # DESTRUCTIVE
# Then trigger collection again
```

### Vector search not working

```bash
# 1. Check vector store health
./hermes-diag sources  # Compare db vs vector counts

# 2. Rebuild vector store from scratch
./hermes-diag rebuild-vectors

# 3. Verify search is working
# (Test in UI or via API)
```

---

## Tips

- **Color output**: The CLI uses ANSI colors for better readability
- **Partial matching**: Customer names can be partial (e.g., "ANZ" matches "ANZ Bank")
- **Quick check**: Use `./hermes-diag all` for a comprehensive health check
- **After changes**: Always run `./hermes-diag config` after editing `customers.yaml`
- **Clean output**: SQL queries are hidden by default. Use `--debug` to see them
- **Debug mode**: Use `--debug` flag when you need to see database queries for troubleshooting

---

## Developer/Debug Scripts

Some specialized scripts remain for advanced debugging:

- `debug_clustering.py` - Debug clustering similarity calculations
- `debug_selectors.py` - Debug web scraping CSS selectors (Playwright)
- `test_*.py` - Unit tests for various components (use with pytest)

These are intentionally kept separate as they're developer tools, not routine diagnostics.

---

## Examples

**Quick health check:**
```bash
./hermes-diag all
```

**Debug Reddit collection:**
```bash
./hermes-diag reddit
./hermes-diag reddit-processed
```

**Test ANZ Bank feed:**
```bash
./hermes-diag api-feed ANZ
```

**Sync config after editing YAML:**
```bash
./hermes-diag sync-config
./hermes-diag config  # Verify sync worked
```

**Recluster all items:**
```bash
./hermes-diag backfill-clustering
# Or skip confirmation:
./hermes-diag backfill-clustering --force
```

**Check LinkedIn post dates:**
```bash
./hermes-diag linkedin-dates
```

**Rebuild vector store:**
```bash
./hermes-diag rebuild-vectors
# Or skip confirmation:
./hermes-diag rebuild-vectors --force
```

**Delete LinkedIn data (DESTRUCTIVE):**
```bash
./hermes-diag delete-linkedin-posts      # Delete ALL posts
./hermes-diag delete-linkedin-profiles   # Delete only profile items
# Use --force to skip confirmation (dangerous):
./hermes-diag delete-linkedin-posts --force
```
