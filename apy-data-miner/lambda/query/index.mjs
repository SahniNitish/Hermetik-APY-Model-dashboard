/**
 * Query & Export Lambda - Export feature-engineered dataset for ML training
 */

import pg from 'pg';
import { SecretsManagerClient, GetSecretValueCommand } from '@aws-sdk/client-secrets-manager';
import { S3Client, PutObjectCommand } from '@aws-sdk/client-s3';

const { Pool } = pg;
const s3 = new S3Client({ region: 'us-east-1' });
const BUCKET = 'apy-data-miner-exports-226208942523';

const STABLECOINS = ['USDC', 'USDT', 'DAI', 'FRAX', 'BUSD', 'TUSD', 'USDP', 'GUSD', 'LUSD', 'sUSD', 'USDD', 'crvUSD', 'GHO', 'PYUSD'];

async function getCredentials() {
  const client = new SecretsManagerClient({ region: 'us-east-1' });
  const command = new GetSecretValueCommand({
    SecretId: process.env.DB_SECRETS_ARN || 'apy-data-miner/dev/database'
  });
  const response = await client.send(command);
  return JSON.parse(response.SecretString);
}

function isStablecoin(symbol) {
  return STABLECOINS.includes(symbol?.toUpperCase());
}

function getStablecoinPairType(token0Symbol, token1Symbol) {
  const t0Stable = isStablecoin(token0Symbol);
  const t1Stable = isStablecoin(token1Symbol);
  if (t0Stable && t1Stable) return 'stable_stable';
  if (t0Stable || t1Stable) return 'stable_other';
  return 'other';
}

function getActivityLevel(txCount) {
  if (txCount >= 20) return 'high';
  if (txCount >= 5) return 'medium';
  return 'low';
}

function getPoolMaturity(daysSinceStart) {
  if (daysSinceStart < 7) return 'new';
  if (daysSinceStart < 30) return 'young';
  if (daysSinceStart < 90) return 'mature';
  return 'established';
}

function getVolatilityLevel(std, avg) {
  if (avg === 0) return '';
  const cv = std / avg;
  if (cv < 0.3) return 'low_vol';
  if (cv < 0.7) return 'medium_vol';
  return 'high_vol';
}

function calculateRollingStats(values, windowSize) {
  if (values.length < windowSize) {
    const sum = values.reduce((a, b) => a + b, 0);
    return { avg: sum / values.length, std: 0 };
  }
  const window = values.slice(-windowSize);
  const avg = window.reduce((a, b) => a + b, 0) / windowSize;
  const variance = window.reduce((sum, val) => sum + Math.pow(val - avg, 2), 0) / windowSize;
  return { avg, std: Math.sqrt(variance) };
}

function toCSV(rows, columns) {
  const header = columns.join(',');
  const lines = rows.map(row => columns.map(col => {
    const val = row[col];
    if (val === null || val === undefined) return '';
    if (typeof val === 'string' && val.includes(',')) return `"${val}"`;
    return val;
  }).join(','));
  return [header, ...lines].join('\n');
}

export const handler = async (event) => {
  const creds = await getCredentials();

  const pool = new Pool({
    host: creds.host,
    port: creds.port || 5432,
    database: creds.database || 'apyminer',
    user: creds.username,
    password: creds.password,
    ssl: { rejectUnauthorized: false }
  });

  try {
    const today = new Date().toISOString().split('T')[0];

    // Get all daily metrics with pool info, ordered by pool and date
    const result = await pool.query(`
      SELECT dm.pool_address, dm.date, dm.tx_count, dm.unique_users,
             p.token0_symbol, p.token1_symbol, p.fee_tier, p.pool_type
      FROM daily_metrics dm
      JOIN pools p ON dm.pool_address = p.pool_address
      ORDER BY dm.pool_address, dm.date ASC
    `);

    // Group by pool
    const poolData = {};
    for (const row of result.rows) {
      if (!poolData[row.pool_address]) {
        poolData[row.pool_address] = [];
      }
      poolData[row.pool_address].push(row);
    }

    // Feature engineering
    const featureRows = [];

    for (const [poolAddress, rows] of Object.entries(poolData)) {
      const txHistory = [];
      let cumulative = 0;
      const startDate = new Date(rows[0].date);

      for (let i = 0; i < rows.length; i++) {
        const row = rows[i];
        const txCount = row.tx_count;
        txHistory.push(txCount);
        cumulative += txCount;

        const currentDate = new Date(row.date);
        const daysSinceStart = Math.floor((currentDate - startDate) / (1000 * 60 * 60 * 24));
        const dayNumber = i + 1;

        // Rolling stats
        const stats3d = calculateRollingStats(txHistory, 3);
        const stats7d = calculateRollingStats(txHistory, 7);

        // Growth rate (compared to previous day)
        const prevTx = i > 0 ? rows[i - 1].tx_count : txCount;
        const txGrowthRate = prevTx !== 0 ? (txCount - prevTx) / prevTx : 0;

        // Future targets (for training data)
        let target3dAhead = null, target3dAvgAhead = null;
        let target7dAhead = null, target7dAvgAhead = null;

        if (i + 3 < rows.length) {
          target3dAhead = rows[i + 3].tx_count;
          const future3 = rows.slice(i + 1, i + 4).map(r => r.tx_count);
          target3dAvgAhead = future3.reduce((a, b) => a + b, 0) / future3.length;
        }

        if (i + 7 < rows.length) {
          target7dAhead = rows[i + 7].tx_count;
          const future7 = rows.slice(i + 1, i + 8).map(r => r.tx_count);
          target7dAvgAhead = future7.reduce((a, b) => a + b, 0) / future7.length;
        }

        const poolName = row.token0_symbol && row.token1_symbol
          ? `${row.token0_symbol}/${row.token1_symbol}`
          : 'Unknown Pool';

        const feePercentage = row.fee_tier ? row.fee_tier / 1000000 : 0;

        featureRows.push({
          poolAddress: row.pool_address,
          date: row.date.toISOString().split('T')[0],
          tx_count: txCount,
          unique_users: row.unique_users,
          pool_name: poolName,
          token0Symbol: row.token0_symbol || 'TOKEN0',
          token1Symbol: row.token1_symbol || 'TOKEN1',
          fee: row.fee_tier || 0,
          fee_percentage: feePercentage,
          poolType: row.pool_type || 'other',
          tx_count_3d_avg: stats3d.avg,
          tx_count_7d_avg: stats7d.avg,
          tx_count_7d_std: stats7d.std,
          tx_count_cumulative: cumulative,
          days_since_start: daysSinceStart,
          day_number: dayNumber,
          tx_growth_rate: txGrowthRate,
          target_tx_3d_ahead: target3dAhead,
          target_tx_3d_avg_ahead: target3dAvgAhead,
          target_tx_7d_ahead: target7dAhead,
          target_tx_7d_avg_ahead: target7dAvgAhead,
          stablecoin_pair_type: getStablecoinPairType(row.token0_symbol, row.token1_symbol),
          activity_level: getActivityLevel(txCount),
          pool_maturity: getPoolMaturity(daysSinceStart),
          volatility_level: getVolatilityLevel(stats7d.std, stats7d.avg)
        });
      }
    }

    // Sort by date desc, tx_count desc
    featureRows.sort((a, b) => {
      if (a.date !== b.date) return b.date.localeCompare(a.date);
      return b.tx_count - a.tx_count;
    });

    const columns = [
      'poolAddress', 'date', 'tx_count', 'unique_users', 'pool_name',
      'token0Symbol', 'token1Symbol', 'fee', 'fee_percentage', 'poolType',
      'tx_count_3d_avg', 'tx_count_7d_avg', 'tx_count_7d_std', 'tx_count_cumulative',
      'days_since_start', 'day_number', 'tx_growth_rate',
      'target_tx_3d_ahead', 'target_tx_3d_avg_ahead', 'target_tx_7d_ahead', 'target_tx_7d_avg_ahead',
      'stablecoin_pair_type', 'activity_level', 'pool_maturity', 'volatility_level'
    ];

    const fullDatasetCSV = toCSV(featureRows, columns);

    // Upload full dataset
    await s3.send(new PutObjectCommand({
      Bucket: BUCKET,
      Key: `pool_dataset_${today}.csv`,
      Body: fullDatasetCSV,
      ContentType: 'text/csv'
    }));

    await s3.send(new PutObjectCommand({
      Bucket: BUCKET,
      Key: 'pool_dataset_latest.csv',
      Body: fullDatasetCSV,
      ContentType: 'text/csv'
    }));

    // Split into training (80%) and test (20%)
    const shuffled = [...featureRows].sort(() => Math.random() - 0.5);
    const splitIdx = Math.floor(shuffled.length * 0.8);
    const trainingData = shuffled.slice(0, splitIdx);
    const testData = shuffled.slice(splitIdx);

    const trainingCSV = toCSV(trainingData, columns);
    const testCSV = toCSV(testData, columns);

    await s3.send(new PutObjectCommand({
      Bucket: BUCKET,
      Key: `pool_training_data_${today}.csv`,
      Body: trainingCSV,
      ContentType: 'text/csv'
    }));

    await s3.send(new PutObjectCommand({
      Bucket: BUCKET,
      Key: 'pool_training_data_latest.csv',
      Body: trainingCSV,
      ContentType: 'text/csv'
    }));

    await s3.send(new PutObjectCommand({
      Bucket: BUCKET,
      Key: `pool_test_data_${today}.csv`,
      Body: testCSV,
      ContentType: 'text/csv'
    }));

    await s3.send(new PutObjectCommand({
      Bucket: BUCKET,
      Key: 'pool_test_data_latest.csv',
      Body: testCSV,
      ContentType: 'text/csv'
    }));

    return {
      statusCode: 200,
      body: JSON.stringify({
        message: 'Feature-engineered dataset exported to S3',
        bucket: BUCKET,
        files: [
          `pool_dataset_${today}.csv`,
          'pool_dataset_latest.csv',
          `pool_training_data_${today}.csv`,
          'pool_training_data_latest.csv',
          `pool_test_data_${today}.csv`,
          'pool_test_data_latest.csv'
        ],
        stats: {
          total_rows: featureRows.length,
          unique_pools: Object.keys(poolData).length,
          training_rows: trainingData.length,
          test_rows: testData.length
        }
      }, null, 2)
    };
  } finally {
    await pool.end();
  }
};
