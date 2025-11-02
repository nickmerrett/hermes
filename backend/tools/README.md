# Hermes Utility Tools

This directory contains utility scripts for database maintenance, migrations, and troubleshooting.

## Available Tools

### Database Migrations

#### `add_platform_settings.py`
Creates the platform_settings table for configurable system settings.

**What it does:**
- Creates `platform_settings` table with key-value JSON storage
- Initializes default settings for:
  - Daily briefing prompts and templates
  - AI model configuration
  - Collection schedules and retention policies
  - Story clustering parameters
  - Collector-specific settings (Reddit, etc.)

**Usage:**
```bash
cd /app  # If in Docker container
python tools/add_platform_settings.py

# Or from host:
docker exec -it atl-intel-backend-1 python /app/tools/add_platform_settings.py
```

**When to use:**
- After upgrading to a version with the Platform Settings UI feature
- On first deployment if platform_settings table doesn't exist
- Safe to run multiple times (checks if table already exists)

---

#### `migrate_ai_processing_fields.py`
Adds AI processing status tracking fields to the database schema.

**What it does:**
- Adds `needs_reprocessing`, `processing_attempts`, `last_processing_error`, `last_processing_attempt` to `processed_intelligence` table
- Adds `items_failed_processing` to `collection_jobs` table
- Creates indexes for performance

**Usage:**
```bash
cd /app  # If in Docker container
python tools/migrate_ai_processing_fields.py

# Or from host:
docker exec -it <container-name> python /app/tools/migrate_ai_processing_fields.py
```

**When to use:**
- After upgrading to a version with AI failure handling features
- If you see database schema errors related to AI processing fields

---

#### `migrate_collection_status.py`
Adds the collection_status table for tracking collector errors per customer/source.

**What it does:**
- Creates `collection_status` table
- Tracks status per customer and source type (reddit, linkedin_user, etc.)
- Stores error messages, consecutive failure counts, last success time
- Helps identify which collectors are failing and why

**Usage:**
```bash
cd /app
python tools/migrate_collection_status.py
```

**When to use:**
- After upgrading to a version with collection status tracking
- If you want to monitor collector health per customer

---

### Vector Store Management

#### `rebuild_vector_store.py`
Rebuilds the ChromaDB vector store from scratch.

**What it does:**
- Deletes existing vector store collection
- Re-embeds all intelligence items from the database
- Recreates the vector store with correct distance metrics

**Usage:**
```bash
cd /app
python tools/rebuild_vector_store.py
```

**When to use:**
- After changing embedding models
- If vector search results seem incorrect
- When upgrading ChromaDB versions
- If the vector store becomes corrupted

**Warning:** This process can take several minutes for large datasets.

---

### LinkedIn Data Cleanup

#### `check_linkedin_dates.py`
Diagnostic tool to check LinkedIn post dates.

**What it does:**
- Queries LinkedIn posts from the database
- Displays post titles, dates, and collected dates
- Helps identify date parsing issues

**Usage:**
```bash
python tools/check_linkedin_dates.py
```

**When to use:**
- Troubleshooting LinkedIn date display issues
- Verifying LinkedIn collector is working correctly

---

#### `delete_linkedin_posts.py`
Removes all LinkedIn posts from the database.

**What it does:**
- Deletes all intelligence items with `source_type = 'linkedin_post'`
- Removes associated processed intelligence and vector embeddings
- Useful for cleaning up test data or incorrect collections

**Usage:**
```bash
python tools/delete_linkedin_posts.py
```

**Warning:** This is destructive and cannot be undone. Use with caution.

**When to use:**
- Clearing out old/incorrect LinkedIn post data
- Resetting LinkedIn collections after configuration changes

---

#### `delete_linkedin_profiles.py`
Removes LinkedIn profile items (not posts) from the database.

**What it does:**
- Deletes intelligence items from LinkedIn profiles
- Cleans up profile-based collections that shouldn't be news items

**Usage:**
```bash
python tools/delete_linkedin_profiles.py
```

**Warning:** This is destructive and cannot be undone.

**When to use:**
- Removing LinkedIn profile information that was collected as news
- Cleaning up after LinkedIn collector configuration errors

---

### Debugging Tools

#### `debug_clustering.py`
Diagnostic tool to debug story clustering issues.

**What it does:**
- Compares vector embeddings between items
- Calculates similarity scores
- Shows why items are/aren't being clustered together
- Helps tune clustering thresholds

**Usage:**
```bash
python tools/debug_clustering.py
```

**When to use:**
- Investigating why similar stories aren't clustering
- Tuning similarity thresholds
- Debugging clustering logic

---

#### `debug_selectors.py`
Web scraping selector debugging tool.

**What it does:**
- Tests CSS selectors against web pages
- Validates web scraping source configurations
- Helps troubleshoot scraping issues

**Usage:**
```bash
python tools/debug_selectors.py
```

**When to use:**
- Setting up new web scraping sources
- Debugging failed web scraping collections
- Validating CSS selectors

---

#### `verify_collection_status.py`
Quick verification tool for collection_status table.

**What it does:**
- Checks if collection_status table exists
- Shows table structure
- Displays current collection statuses

**Usage:**
```bash
python tools/verify_collection_status.py
```

**When to use:**
- Verifying migration ran successfully
- Quick check of collector health status

---

## Running Tools in Docker

All tools can be run inside the Docker container:

```bash
# Interactive shell
docker exec -it atl-intel-backend-1 bash
cd /app
python tools/<script-name>.py

# Single command
docker exec -it atl-intel-backend-1 python /app/tools/<script-name>.py
```

## Safety Notes

1. **Always backup your database before running destructive tools**
   ```bash
   cp data/db/intelligence.db data/db/intelligence.db.backup
   ```

2. **Test in development first** - Don't run untested tools in production

3. **Check logs** - Most tools provide detailed logging about what they're doing

4. **Verify results** - After running a tool, check the dashboard to ensure everything looks correct

## Need Help?

If you encounter issues with any of these tools:
1. Check the tool's output/error messages
2. Review the backend logs: `docker logs atl-intel-backend-1`
3. Ensure your database is not corrupted: `sqlite3 data/db/intelligence.db "PRAGMA integrity_check;"`
