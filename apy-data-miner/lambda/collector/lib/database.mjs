/**
 * Database Module
 * Handles PostgreSQL connections and queries
 */

import pg from 'pg';
import { SecretsManagerClient, GetSecretValueCommand } from '@aws-sdk/client-secrets-manager';

const { Pool } = pg;

let pool = null;

/**
 * Get database credentials from Secrets Manager or environment
 */
async function getDatabaseCredentials() {
  // For local development
  if (process.env.DB_HOST) {
    return {
      host: process.env.DB_HOST,
      port: parseInt(process.env.DB_PORT || '5432'),
      database: process.env.DB_NAME,
      user: process.env.DB_USER,
      password: process.env.DB_PASSWORD
    };
  }

  // For AWS Lambda - fetch from Secrets Manager
  const client = new SecretsManagerClient({ region: process.env.AWS_REGION || 'us-east-1' });

  const command = new GetSecretValueCommand({
    SecretId: process.env.DB_SECRETS_ARN || 'apy-data-miner/database'
  });

  const response = await client.send(command);
  const secrets = JSON.parse(response.SecretString);

  return {
    host: secrets.host,
    port: secrets.port || 5432,
    database: secrets.database || 'apyminer',
    user: secrets.username,
    password: secrets.password
  };
}

/**
 * Initialize database schema (create tables if not exist)
 */
async function initSchema(db) {
  const schema = `
    CREATE TABLE IF NOT EXISTS pools (
      pool_address VARCHAR(42) PRIMARY KEY,
      token0 VARCHAR(42) NOT NULL,
      token1 VARCHAR(42) NOT NULL,
      token0_symbol VARCHAR(20),
      token1_symbol VARCHAR(20),
      fee_tier INTEGER NOT NULL,
      pool_type VARCHAR(20) NOT NULL,
      created_at TIMESTAMP DEFAULT NOW(),
      updated_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS daily_metrics (
      id SERIAL PRIMARY KEY,
      pool_address VARCHAR(42) NOT NULL REFERENCES pools(pool_address),
      date DATE NOT NULL,
      tx_count INTEGER NOT NULL DEFAULT 0,
      unique_users INTEGER NOT NULL DEFAULT 0,
      created_at TIMESTAMP DEFAULT NOW(),
      updated_at TIMESTAMP DEFAULT NOW(),
      UNIQUE(pool_address, date)
    );

    CREATE INDEX IF NOT EXISTS idx_daily_metrics_date ON daily_metrics(date);
    CREATE INDEX IF NOT EXISTS idx_daily_metrics_pool ON daily_metrics(pool_address);
    CREATE INDEX IF NOT EXISTS idx_pools_type ON pools(pool_type);
  `;

  await db.query(schema);
  console.log('Database schema initialized');
}

/**
 * Initialize database connection pool
 */
export async function initDatabase() {
  if (pool) return pool;

  const credentials = await getDatabaseCredentials();

  pool = new Pool({
    ...credentials,
    max: 5,
    idleTimeoutMillis: 30000,
    connectionTimeoutMillis: 10000,
    ssl: process.env.DB_SSL === 'true' ? { rejectUnauthorized: false } : false
  });

  // Test connection
  const client = await pool.connect();
  await client.query('SELECT NOW()');
  client.release();

  // Initialize schema
  await initSchema(pool);

  return pool;
}

/**
 * Close database connection
 */
export async function closeDatabase() {
  if (pool) {
    await pool.end();
    pool = null;
  }
}

/**
 * Get set of existing pool addresses
 */
export async function getExistingPools(db) {
  const result = await db.query('SELECT pool_address FROM pools');
  return new Set(result.rows.map(r => r.pool_address.toLowerCase()));
}

/**
 * Save a new pool to database
 */
export async function savePool(db, poolData) {
  const query = `
    INSERT INTO pools (pool_address, token0, token1, token0_symbol, token1_symbol, fee_tier, pool_type)
    VALUES ($1, $2, $3, $4, $5, $6, $7)
    ON CONFLICT (pool_address) DO UPDATE SET
      token0_symbol = EXCLUDED.token0_symbol,
      token1_symbol = EXCLUDED.token1_symbol,
      updated_at = NOW()
  `;

  await db.query(query, [
    poolData.poolAddress.toLowerCase(),
    poolData.token0,
    poolData.token1,
    poolData.token0Symbol,
    poolData.token1Symbol,
    poolData.feeTier,
    poolData.poolType
  ]);
}

/**
 * Save daily metrics for a pool
 */
export async function saveDailyMetrics(db, metrics) {
  const query = `
    INSERT INTO daily_metrics (pool_address, date, tx_count, unique_users)
    VALUES ($1, $2, $3, $4)
    ON CONFLICT (pool_address, date) DO UPDATE SET
      tx_count = EXCLUDED.tx_count,
      unique_users = EXCLUDED.unique_users,
      updated_at = NOW()
  `;

  await db.query(query, [
    metrics.poolAddress.toLowerCase(),
    metrics.date,
    metrics.txCount,
    metrics.uniqueUsers
  ]);
}

/**
 * Save raw transactions (optional - for detailed analysis)
 */
export async function saveTransactions(db, transactions) {
  if (transactions.length === 0) return;

  // Batch insert using unnest for efficiency
  const values = transactions.map(tx => [
    tx.blockNumber,
    tx.timestamp,
    tx.txHash,
    tx.poolAddress.toLowerCase(),
    tx.sender,
    tx.recipient,
    tx.amount0,
    tx.amount1
  ]);

  const query = `
    INSERT INTO transactions (block_number, timestamp, tx_hash, pool_address, sender, recipient, amount0, amount1)
    SELECT * FROM UNNEST(
      $1::integer[],
      $2::timestamp[],
      $3::varchar[],
      $4::varchar[],
      $5::varchar[],
      $6::varchar[],
      $7::numeric[],
      $8::numeric[]
    )
    ON CONFLICT (tx_hash, pool_address) DO NOTHING
  `;

  await db.query(query, [
    values.map(v => v[0]),
    values.map(v => v[1]),
    values.map(v => v[2]),
    values.map(v => v[3]),
    values.map(v => v[4]),
    values.map(v => v[5]),
    values.map(v => v[6]),
    values.map(v => v[7])
  ]);
}

/**
 * Get rolling statistics for feature generation (for ML team)
 */
export async function getRollingStats(db, poolAddress, days = 7) {
  const query = `
    SELECT
      pool_address,
      date,
      tx_count,
      unique_users,
      AVG(tx_count) OVER (
        PARTITION BY pool_address
        ORDER BY date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
      ) as tx_count_7d_avg,
      STDDEV(tx_count) OVER (
        PARTITION BY pool_address
        ORDER BY date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
      ) as tx_count_7d_std,
      AVG(tx_count) OVER (
        PARTITION BY pool_address
        ORDER BY date
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
      ) as tx_count_3d_avg,
      SUM(tx_count) OVER (
        PARTITION BY pool_address
        ORDER BY date
      ) as tx_count_cumulative
    FROM daily_metrics
    WHERE pool_address = $1
    ORDER BY date DESC
    LIMIT $2
  `;

  const result = await db.query(query, [poolAddress.toLowerCase(), days]);
  return result.rows;
}

/**
 * Get latest metrics for all pools (for predictions)
 */
export async function getLatestMetricsForAllPools(db) {
  const query = `
    WITH latest_dates AS (
      SELECT pool_address, MAX(date) as latest_date
      FROM daily_metrics
      GROUP BY pool_address
    ),
    rolling_stats AS (
      SELECT
        dm.pool_address,
        dm.date,
        dm.tx_count,
        dm.unique_users,
        AVG(dm.tx_count) OVER w as tx_count_7d_avg,
        STDDEV(dm.tx_count) OVER w as tx_count_7d_std,
        AVG(dm.tx_count) OVER w3 as tx_count_3d_avg,
        SUM(dm.tx_count) OVER (PARTITION BY dm.pool_address ORDER BY dm.date) as tx_count_cumulative,
        LAG(dm.tx_count, 1) OVER (PARTITION BY dm.pool_address ORDER BY dm.date) as prev_tx_count
      FROM daily_metrics dm
      WINDOW
        w AS (PARTITION BY dm.pool_address ORDER BY dm.date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW),
        w3 AS (PARTITION BY dm.pool_address ORDER BY dm.date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)
    )
    SELECT
      rs.*,
      p.token0_symbol,
      p.token1_symbol,
      p.fee_tier,
      p.pool_type,
      CASE
        WHEN rs.prev_tx_count > 0 THEN (rs.tx_count - rs.prev_tx_count)::float / rs.prev_tx_count
        ELSE 0
      END as tx_growth_rate
    FROM rolling_stats rs
    JOIN latest_dates ld ON rs.pool_address = ld.pool_address AND rs.date = ld.latest_date
    JOIN pools p ON rs.pool_address = p.pool_address
  `;

  const result = await db.query(query);
  return result.rows;
}
