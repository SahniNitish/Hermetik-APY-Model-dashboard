/**
 * APY Data Miner - Daily Collector Lambda
 * Collects Uniswap V3 swap transactions for the past 24 hours
 * and stores them in RDS PostgreSQL
 */

import { getSwapLogs, getBlockRange } from './lib/ethereum.mjs';
import { classifyPool, fetchPoolMetadata, fetchTokenMetadata } from './lib/classifier.mjs';
import {
  initDatabase,
  saveTransactions,
  saveDailyMetrics,
  savePool,
  getExistingPools,
  closeDatabase
} from './lib/database.mjs';

// Configuration
const BLOCKS_PER_DAY = 7200;
const BATCH_SIZE = 1000;
const DELAY_MS = 500;

const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

/**
 * Aggregate transactions into daily metrics per pool
 */
function aggregateMetrics(transactions, date) {
  const poolMetrics = new Map();

  for (const tx of transactions) {
    const poolAddress = tx.poolAddress.toLowerCase();

    if (!poolMetrics.has(poolAddress)) {
      poolMetrics.set(poolAddress, {
        poolAddress,
        date,
        txCount: 0,
        uniqueUsers: new Set(),
        totalAmount0: BigInt(0),
        totalAmount1: BigInt(0)
      });
    }

    const metrics = poolMetrics.get(poolAddress);
    metrics.txCount++;
    metrics.uniqueUsers.add(tx.sender);
    metrics.uniqueUsers.add(tx.recipient);
  }

  // Convert Sets to counts
  return Array.from(poolMetrics.values()).map(m => ({
    poolAddress: m.poolAddress,
    date: m.date,
    txCount: m.txCount,
    uniqueUsers: m.uniqueUsers.size
  }));
}

/**
 * Process new pools that haven't been seen before
 */
async function processNewPools(poolAddresses, existingPools) {
  const newPools = poolAddresses.filter(addr => !existingPools.has(addr));

  if (newPools.length === 0) {
    console.log('No new pools to classify');
    return [];
  }

  console.log(`Classifying ${newPools.length} new pools...`);
  const classifiedPools = [];

  for (let i = 0; i < newPools.length; i += 50) {
    const batch = newPools.slice(i, i + 50);

    const results = await Promise.all(
      batch.map(async (poolAddress) => {
        try {
          const poolMeta = await fetchPoolMetadata(poolAddress);
          if (!poolMeta) return null;

          const [token0Meta, token1Meta] = await Promise.all([
            fetchTokenMetadata(poolMeta.token0),
            fetchTokenMetadata(poolMeta.token1)
          ]);

          const poolType = classifyPool(poolMeta.token0, poolMeta.token1);

          return {
            poolAddress,
            token0: poolMeta.token0,
            token1: poolMeta.token1,
            token0Symbol: token0Meta.symbol,
            token1Symbol: token1Meta.symbol,
            feeTier: parseInt(poolMeta.fee),
            poolType
          };
        } catch (error) {
          console.error(`Failed to classify pool ${poolAddress}:`, error.message);
          return null;
        }
      })
    );

    classifiedPools.push(...results.filter(r => r !== null));

    if (i + 50 < newPools.length) {
      await sleep(DELAY_MS);
    }
  }

  return classifiedPools;
}

/**
 * Main Lambda handler
 */
export const handler = async (event, context) => {
  console.log('Starting APY Data Miner - Daily Collection');
  console.log('Event:', JSON.stringify(event));

  const startTime = Date.now();
  let db = null;

  try {
    // Initialize database connection
    db = await initDatabase();
    console.log('Database connected');

    // Get block range for past 24 hours
    const { startBlock, endBlock, currentBlock } = await getBlockRange(BLOCKS_PER_DAY);
    console.log(`Block range: ${startBlock} - ${endBlock} (${endBlock - startBlock} blocks)`);

    // Collect swap logs in batches
    const allTransactions = [];
    let currentBlockNum = startBlock;
    let batchNum = 0;
    const totalBatches = Math.ceil((endBlock - startBlock) / BATCH_SIZE);

    while (currentBlockNum <= endBlock) {
      batchNum++;
      const batchEnd = Math.min(currentBlockNum + BATCH_SIZE - 1, endBlock);

      console.log(`Fetching batch ${batchNum}/${totalBatches}: blocks ${currentBlockNum}-${batchEnd}`);

      try {
        const logs = await getSwapLogs(currentBlockNum, batchEnd);
        allTransactions.push(...logs);
        console.log(`  Got ${logs.length} swaps (total: ${allTransactions.length})`);
      } catch (error) {
        console.error(`  Error in batch ${batchNum}:`, error.message);
        // Continue with next batch
      }

      currentBlockNum = batchEnd + 1;

      if (currentBlockNum <= endBlock) {
        await sleep(DELAY_MS);
      }
    }

    console.log(`Total transactions collected: ${allTransactions.length}`);

    if (allTransactions.length === 0) {
      return {
        statusCode: 200,
        body: JSON.stringify({
          message: 'No transactions found for the period',
          blocksProcessed: endBlock - startBlock,
          duration: `${((Date.now() - startTime) / 1000).toFixed(1)}s`
        })
      };
    }

    // Get unique pools
    const uniquePools = [...new Set(allTransactions.map(tx => tx.poolAddress.toLowerCase()))];
    console.log(`Unique pools with activity: ${uniquePools.length}`);

    // Get existing pools from database
    const existingPools = await getExistingPools(db);
    console.log(`Existing pools in DB: ${existingPools.size}`);

    // Classify and save new pools
    const newPools = await processNewPools(uniquePools, existingPools);
    if (newPools.length > 0) {
      for (const pool of newPools) {
        await savePool(db, pool);
      }
      console.log(`Saved ${newPools.length} new pools`);
    }

    // Get updated pool list (including newly added)
    const allKnownPools = await getExistingPools(db);
    console.log(`Total known pools in DB: ${allKnownPools.size}`);

    // Aggregate daily metrics
    const today = new Date().toISOString().split('T')[0];
    const dailyMetrics = aggregateMetrics(allTransactions, today);
    console.log(`Aggregated metrics for ${dailyMetrics.length} pools`);

    // Save daily metrics (only for pools that exist in DB)
    let savedMetrics = 0;
    let skippedMetrics = 0;
    for (const metrics of dailyMetrics) {
      if (allKnownPools.has(metrics.poolAddress)) {
        await saveDailyMetrics(db, metrics);
        savedMetrics++;
      } else {
        skippedMetrics++;
      }
    }
    console.log(`Daily metrics saved: ${savedMetrics}, skipped: ${skippedMetrics}`);

    // Calculate summary stats
    const totalTxCount = dailyMetrics.reduce((sum, m) => sum + m.txCount, 0);
    const avgTxPerPool = (totalTxCount / dailyMetrics.length).toFixed(1);

    const duration = ((Date.now() - startTime) / 1000).toFixed(1);

    const result = {
      statusCode: 200,
      body: JSON.stringify({
        message: 'Daily collection complete',
        date: today,
        stats: {
          transactionsCollected: allTransactions.length,
          uniquePoolsActive: uniquePools.length,
          newPoolsClassified: newPools.length,
          avgTransactionsPerPool: avgTxPerPool
        },
        blocks: {
          start: startBlock,
          end: endBlock,
          processed: endBlock - startBlock
        },
        duration: `${duration}s`
      })
    };

    console.log('Result:', result.body);
    return result;

  } catch (error) {
    console.error('Lambda execution failed:', error);

    return {
      statusCode: 500,
      body: JSON.stringify({
        error: error.message,
        stack: error.stack
      })
    };
  } finally {
    if (db) {
      await closeDatabase(db);
      console.log('Database connection closed');
    }
  }
};

// For local testing
if (process.env.LOCAL_TEST) {
  handler({}, {}).then(console.log).catch(console.error);
}
