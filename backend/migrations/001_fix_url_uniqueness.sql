-- Migration: Allow same URL to be collected for multiple customers
--
-- Problem: Currently URL is globally unique, meaning if Westpac collects
-- an article about ANZ, ANZ cannot collect the same article.
--
-- Solution: Change to composite unique constraint (customer_id, url)

-- Step 1: Create new table with correct schema
CREATE TABLE intelligence_items_new (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    source_id INTEGER,
    source_type VARCHAR(50) NOT NULL,
    title TEXT NOT NULL,
    content TEXT,
    url VARCHAR(2048),
    published_date DATETIME,
    collected_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    raw_data JSON,
    cluster_id VARCHAR(36),
    is_cluster_primary BOOLEAN DEFAULT 0,
    source_tier VARCHAR(20),
    cluster_member_count INTEGER DEFAULT 1,
    ignored BOOLEAN DEFAULT 0,
    ignored_at DATETIME,

    FOREIGN KEY (customer_id) REFERENCES customers(id),
    FOREIGN KEY (source_id) REFERENCES sources(id),

    -- NEW: Unique per customer, not globally
    UNIQUE(customer_id, url)
);

-- Step 2: Copy all data
INSERT INTO intelligence_items_new
SELECT * FROM intelligence_items;

-- Step 3: Drop old table (this also drops its indexes)
DROP TABLE intelligence_items;

-- Step 4: Rename new table
ALTER TABLE intelligence_items_new RENAME TO intelligence_items;

-- Step 5: Create indexes (now the names are free)
CREATE INDEX ix_intelligence_items_customer_id ON intelligence_items(customer_id);
CREATE INDEX ix_intelligence_items_source_type ON intelligence_items(source_type);
CREATE INDEX ix_intelligence_items_url ON intelligence_items(url);
CREATE INDEX ix_intelligence_items_published_date ON intelligence_items(published_date);
CREATE INDEX ix_intelligence_items_collected_date ON intelligence_items(collected_date);
CREATE INDEX ix_intelligence_items_cluster_id ON intelligence_items(cluster_id);
CREATE INDEX ix_intelligence_items_is_cluster_primary ON intelligence_items(is_cluster_primary);
CREATE INDEX ix_intelligence_items_ignored ON intelligence_items(ignored);

-- Done! Now the same URL can exist for different customers.
