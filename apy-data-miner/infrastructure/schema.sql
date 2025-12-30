-- APY Data Miner - PostgreSQL Schema
-- Database: apyminer
--
-- This schema is designed for:
-- 1. Daily collection of Uniswap V3 swap data
-- 2. ML team to query for training/inference
-- 3. Feature engineering with rolling statistics

-- Create database (run separately as superuser)
-- CREATE DATABASE apyminer;

-- Connect to apyminer database before running the rest

-----------------------------------------------------------
-- CORE TABLES
-----------------------------------------------------------

-- Pools table: Metadata for all discovered Uniswap V3 pools
CREATE TABLE IF NOT EXISTS pools (
    pool_address    VARCHAR(42) PRIMARY KEY,
    token0          VARCHAR(42) NOT NULL,
    token1          VARCHAR(42) NOT NULL,
    token0_symbol   VARCHAR(20),
    token1_symbol   VARCHAR(20),
    fee_tier        INTEGER NOT NULL,  -- 500 = 0.05%, 3000 = 0.3%, 10000 = 1%
    pool_type       VARCHAR(20) NOT NULL CHECK (pool_type IN ('eth_paired', 'stablecoin', 'other')),
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

-- Daily metrics: Aggregated daily statistics per pool
CREATE TABLE IF NOT EXISTS daily_metrics (
    id              SERIAL PRIMARY KEY,
    pool_address    VARCHAR(42) NOT NULL REFERENCES pools(pool_address),
    date            DATE NOT NULL,
    tx_count        INTEGER NOT NULL DEFAULT 0,
    unique_users    INTEGER NOT NULL DEFAULT 0,
    volume_token0   NUMERIC(78, 0),  -- Raw token amounts (can be huge)
    volume_token1   NUMERIC(78, 0),
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE(pool_address, date)
);

-- Optional: Raw transactions table (if you need granular data)
-- Warning: This table will grow very large (~240K rows/day)
CREATE TABLE IF NOT EXISTS transactions (
    id              BIGSERIAL PRIMARY KEY,
    block_number    INTEGER NOT NULL,
    timestamp       TIMESTAMP NOT NULL,
    tx_hash         VARCHAR(66) NOT NULL,
    pool_address    VARCHAR(42) NOT NULL REFERENCES pools(pool_address),
    sender          VARCHAR(42) NOT NULL,
    recipient       VARCHAR(42) NOT NULL,
    amount0         NUMERIC(78, 0),
    amount1         NUMERIC(78, 0),
    created_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE(tx_hash, pool_address)
);

-- Collection runs: Track each daily collection job
CREATE TABLE IF NOT EXISTS collection_runs (
    id              SERIAL PRIMARY KEY,
    run_date        DATE NOT NULL,
    start_block     INTEGER NOT NULL,
    end_block       INTEGER NOT NULL,
    transactions_collected INTEGER,
    pools_active    INTEGER,
    pools_new       INTEGER,
    duration_seconds NUMERIC(10, 2),
    status          VARCHAR(20) NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
    error_message   TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);

-----------------------------------------------------------
-- INDEXES FOR PERFORMANCE
-----------------------------------------------------------

-- Daily metrics indexes (heavily queried by ML team)
CREATE INDEX IF NOT EXISTS idx_daily_metrics_date ON daily_metrics(date);
CREATE INDEX IF NOT EXISTS idx_daily_metrics_pool ON daily_metrics(pool_address);
CREATE INDEX IF NOT EXISTS idx_daily_metrics_pool_date ON daily_metrics(pool_address, date);

-- Pool indexes
CREATE INDEX IF NOT EXISTS idx_pools_type ON pools(pool_type);
CREATE INDEX IF NOT EXISTS idx_pools_fee ON pools(fee_tier);

-- Transaction indexes (if using transactions table)
CREATE INDEX IF NOT EXISTS idx_transactions_pool ON transactions(pool_address);
CREATE INDEX IF NOT EXISTS idx_transactions_timestamp ON transactions(timestamp);
CREATE INDEX IF NOT EXISTS idx_transactions_block ON transactions(block_number);

-----------------------------------------------------------
-- VIEWS FOR ML TEAM
-----------------------------------------------------------

-- View: Latest metrics with rolling statistics
-- This is what the ML team queries for training data
CREATE OR REPLACE VIEW v_pool_features AS
WITH rolling_stats AS (
    SELECT
        dm.pool_address,
        dm.date,
        dm.tx_count,
        dm.unique_users,
        -- Rolling averages
        AVG(dm.tx_count) OVER w7 as tx_count_7d_avg,
        AVG(dm.tx_count) OVER w3 as tx_count_3d_avg,
        -- Volatility
        STDDEV(dm.tx_count) OVER w7 as tx_count_7d_std,
        -- Cumulative
        SUM(dm.tx_count) OVER (PARTITION BY dm.pool_address ORDER BY dm.date) as tx_count_cumulative,
        -- Growth rate
        LAG(dm.tx_count, 1) OVER (PARTITION BY dm.pool_address ORDER BY dm.date) as prev_tx_count,
        -- Days since first activity
        ROW_NUMBER() OVER (PARTITION BY dm.pool_address ORDER BY dm.date) as days_since_start
    FROM daily_metrics dm
    WINDOW
        w7 AS (PARTITION BY dm.pool_address ORDER BY dm.date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW),
        w3 AS (PARTITION BY dm.pool_address ORDER BY dm.date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)
)
SELECT
    rs.pool_address,
    rs.date,
    rs.tx_count,
    rs.unique_users,
    rs.tx_count_7d_avg,
    rs.tx_count_3d_avg,
    COALESCE(rs.tx_count_7d_std, 0) as tx_count_7d_std,
    rs.tx_count_cumulative,
    rs.days_since_start,
    CASE
        WHEN rs.prev_tx_count > 0 THEN (rs.tx_count - rs.prev_tx_count)::float / rs.prev_tx_count
        ELSE 0
    END as tx_growth_rate,
    p.token0_symbol,
    p.token1_symbol,
    p.fee_tier,
    p.pool_type,
    p.fee_tier::float / 10000 as fee_percentage
FROM rolling_stats rs
JOIN pools p ON rs.pool_address = p.pool_address;

-- View: Training-ready dataset (last 30 days with targets)
CREATE OR REPLACE VIEW v_training_data AS
SELECT
    f1.pool_address,
    f1.date,
    f1.tx_count,
    f1.unique_users,
    f1.tx_count_7d_avg,
    f1.tx_count_3d_avg,
    f1.tx_count_7d_std,
    f1.tx_count_cumulative,
    f1.days_since_start,
    f1.tx_growth_rate,
    f1.fee_tier,
    f1.fee_percentage,
    f1.pool_type,
    -- Target: Transaction count 7 days ahead
    f2.tx_count as target_tx_7d_ahead,
    -- Target: Average transactions over next 7 days
    AVG(f2.tx_count) OVER (
        PARTITION BY f1.pool_address, f1.date
    ) as target_tx_7d_avg_ahead
FROM v_pool_features f1
LEFT JOIN v_pool_features f2
    ON f1.pool_address = f2.pool_address
    AND f2.date = f1.date + INTERVAL '7 days'
WHERE f1.date >= CURRENT_DATE - INTERVAL '37 days'  -- 30 days + 7 for targets
ORDER BY f1.pool_address, f1.date;

-----------------------------------------------------------
-- UTILITY FUNCTIONS
-----------------------------------------------------------

-- Function: Get feature vector for a specific pool (for real-time predictions)
CREATE OR REPLACE FUNCTION get_pool_features(p_pool_address VARCHAR(42))
RETURNS TABLE (
    pool_address VARCHAR(42),
    tx_count INTEGER,
    unique_users INTEGER,
    tx_count_7d_avg NUMERIC,
    tx_count_3d_avg NUMERIC,
    tx_count_7d_std NUMERIC,
    tx_count_cumulative BIGINT,
    days_since_start BIGINT,
    tx_growth_rate NUMERIC,
    fee_tier INTEGER,
    pool_type VARCHAR(20)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        f.pool_address,
        f.tx_count,
        f.unique_users,
        f.tx_count_7d_avg,
        f.tx_count_3d_avg,
        f.tx_count_7d_std,
        f.tx_count_cumulative,
        f.days_since_start,
        f.tx_growth_rate::NUMERIC,
        f.fee_tier,
        f.pool_type
    FROM v_pool_features f
    WHERE f.pool_address = LOWER(p_pool_address)
    ORDER BY f.date DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Function: Cleanup old transaction data (keep last N days)
CREATE OR REPLACE FUNCTION cleanup_old_transactions(days_to_keep INTEGER DEFAULT 90)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM transactions
    WHERE timestamp < NOW() - (days_to_keep || ' days')::INTERVAL;

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-----------------------------------------------------------
-- GRANTS FOR ML TEAM
-----------------------------------------------------------

-- Create read-only user for ML team
-- Run as superuser:
-- CREATE USER ml_reader WITH PASSWORD 'your_secure_password';

-- Grant read access
GRANT CONNECT ON DATABASE apyminer TO ml_reader;
GRANT USAGE ON SCHEMA public TO ml_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO ml_reader;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO ml_reader;

-- Ensure future tables are also accessible
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO ml_reader;

-----------------------------------------------------------
-- SAMPLE QUERIES FOR ML TEAM
-----------------------------------------------------------

-- Query 1: Get all features for training (last 30 days)
-- SELECT * FROM v_training_data WHERE date >= CURRENT_DATE - 30;

-- Query 2: Get latest features for all pools (for batch predictions)
-- SELECT DISTINCT ON (pool_address) * FROM v_pool_features ORDER BY pool_address, date DESC;

-- Query 3: Get top pools by transaction count
-- SELECT pool_address, SUM(tx_count) as total_txs
-- FROM daily_metrics
-- WHERE date >= CURRENT_DATE - 7
-- GROUP BY pool_address
-- ORDER BY total_txs DESC
-- LIMIT 100;

-- Query 4: Export training dataset as CSV
-- \COPY (SELECT * FROM v_training_data) TO '/tmp/training_data.csv' WITH CSV HEADER;
