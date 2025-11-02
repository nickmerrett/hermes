# Documentation & Utilities Consolidation - November 2025

## Overview
Consolidated documentation and utility scripts for better organization and maintainability after completing Customer Management UI (#12) and Platform Settings (#7) features.

## Changes Made

### 1. Documentation Cleanup

**Removed outdated documents:**
- ❌ `CLEANUP_SUMMARY.md` (outdated, from Oct 30)
- ❌ `STOCK_COLLECTOR_IMPROVEMENTS.md` (feature already documented in ROADMAP)

**Updated ROADMAP.md:**
- ✅ Marked #7 "Platform Settings Configuration" as Complete (expanded from Daily Briefing Prompts)
- ✅ Marked #12 "Customer Management in UI" as Complete
- ✅ Documented all implemented features and technical details

### 2. Utility Scripts Organization

**Moved to `backend/tools/`:**
- ✅ `add_platform_settings.py` (migration script)
- ✅ `debug_clustering.py` (debugging tool)
- ✅ `debug_selectors.py` (web scraping debug)
- ✅ `migrate_collection_status.py` (migration script)
- ✅ `verify_collection_status.py` (verification tool)

**Removed:**
- ❌ `backend/scraped_articles.json` (test data)

**Updated `backend/tools/README.md`:**
- ✅ Added documentation for `add_platform_settings.py`
- ✅ Added documentation for `migrate_collection_status.py`
- ✅ Added "Debugging Tools" section with 3 tools
- ✅ Reorganized for better navigation

### 3. Final Documentation Structure

```
📁 atl-intel/
├── 📄 README.md                          # Main entry point
├── 📄 ROADMAP.md                         # Development roadmap (updated)
├── 📄 DIAGNOSTICS.md                     # hermes-diag CLI reference
├── 📄 CONSOLIDATION_SUMMARY.md           # This document
├── 📄 setup.sh                           # Quick setup script
│
├── 📁 docs/
│   ├── 📄 SETUP.md                       # Installation & configuration
│   ├── 📄 CONFIGURATION.md               # Data sources reference
│   └── 📄 DEVELOPMENT.md                 # Developer guide
│
├── 📁 backend/
│   ├── 📄 hermes-diag                    # Main diagnostic CLI
│   │
│   └── 📁 tools/
│       ├── 📄 README.md                  # Tools documentation (updated)
│       │
│       ├── 🔧 Database Migrations
│       ├── add_platform_settings.py      # Platform settings table (NEW)
│       ├── migrate_ai_processing_fields.py
│       └── migrate_collection_status.py   # Collection status tracking
│       │
│       ├── 🧹 Data Cleanup
│       ├── check_linkedin_dates.py
│       ├── delete_linkedin_posts.py
│       ├── delete_linkedin_profiles.py
│       └── rebuild_vector_store.py
│       │
│       └── 🐛 Debugging Tools
│           ├── debug_clustering.py        # Story clustering debug
│           ├── debug_selectors.py         # Web scraping debug
│           └── verify_collection_status.py # Status verification
│
└── 📁 tests/
    └── (test files)
```

## Tools by Category

### Database Migrations (3 tools)
1. **add_platform_settings.py** - Create platform_settings table (NEW)
2. **migrate_ai_processing_fields.py** - Add AI processing tracking
3. **migrate_collection_status.py** - Add collection status tracking

### Data Cleanup (4 tools)
1. **check_linkedin_dates.py** - Check LinkedIn post dates
2. **delete_linkedin_posts.py** - Remove LinkedIn posts
3. **delete_linkedin_profiles.py** - Remove LinkedIn profiles
4. **rebuild_vector_store.py** - Rebuild ChromaDB index

### Debugging Tools (3 tools)
1. **debug_clustering.py** - Debug story clustering similarity
2. **debug_selectors.py** - Test web scraping selectors
3. **verify_collection_status.py** - Verify collection status table

## Completed Features Documented

### Platform Settings (#7)
Expanded from "Daily Briefing Prompts" to comprehensive platform configuration:

**4 Configuration Tabs:**
1. Daily Briefing (6 templates, custom editor, style options, focus areas)
2. AI Configuration (Claude models, embedding models)
3. Collection & Retention (schedules, retention, clustering)
4. Collector Settings (Reddit engagement filters, AI summarization thresholds)

**25+ Configurable Parameters** across all categories

**Technical:**
- `platform_settings` table with JSON storage
- Settings API endpoints
- Migration script in tools/
- Hot-reloadable for clustering and collectors

### Customer Management UI (#12)
Complete database-first customer management:

**Features:**
- Add/Edit/Delete customers via UI
- All YAML fields represented
- Customer tabs for quick switching
- Gear icon for editing
- Form validation and error handling

**Data Management:**
- Database is source of truth
- YAML import/export via hermes-diag
- Custom file path support (--file/-f)
- Bidirectional sync

## Benefits

✅ **Organized Structure** - All tools in dedicated directory
✅ **Clear Documentation** - Each tool documented with usage examples
✅ **Updated Roadmap** - Completed features properly marked
✅ **No Duplication** - Removed outdated/duplicate documentation
✅ **Easy Discovery** - Tools categorized by purpose
✅ **Up-to-date** - ROADMAP reflects actual implementation

## Quick Reference

### Run Migrations
```bash
# Platform settings (required for new installations)
docker compose exec backend python tools/add_platform_settings.py

# Other migrations (if needed)
docker compose exec backend python tools/migrate_collection_status.py
docker compose exec backend python tools/migrate_ai_processing_fields.py
```

### Debug Issues
```bash
# Check clustering
docker compose exec backend python tools/debug_clustering.py

# Verify collection status
docker compose exec backend python tools/verify_collection_status.py

# Test web scraping selectors
docker compose exec backend python tools/debug_selectors.py
```

### hermes-diag Commands
```bash
# Run all diagnostics
./hermes-diag all

# Import/export customer config
./hermes-diag import-config --file path/to/customers.yaml
./hermes-diag export-config --file path/to/output.yaml

# Check sources and status
./hermes-diag sources
./hermes-diag config
./hermes-diag status
```

## Next Steps

After pulling these changes:

1. **Rebuild containers:**
   ```bash
   docker compose build
   docker compose up -d
   ```

2. **Run platform settings migration:**
   ```bash
   docker compose exec backend python tools/add_platform_settings.py
   ```

3. **Access new features:**
   - Settings button in header → Configure platform
   - Add Customer button → Create customers via UI
   - Customer gear icon → Edit existing customers

---

**Date:** November 2, 2025
**Features Completed:** #7 (Platform Settings), #12 (Customer Management UI)
**Files Moved:** 5 utility scripts to tools/
**Files Removed:** 3 outdated documents
**Documentation Updated:** ROADMAP.md, tools/README.md
