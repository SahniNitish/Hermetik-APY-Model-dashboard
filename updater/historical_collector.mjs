/**
 * Historical Data Collector - Fetch 30 days of pool data
 * Collects ALL pool types (ETH, stablecoins, tokens)
 * Handles rate limits with batching
 */

import { ethers } from 'ethers';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import dotenv from 'dotenv';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Load environment variables
dotenv.config({ path: path.join(__dirname, '.env') });

const ALCHEMY_API_KEY = process.env.ALCHEMY_API_KEY;
if (!ALCHEMY_API_KEY) {
  throw new Error('ALCHEMY_API_KEY not found in .env file');
}

// Alchemy provider
const provider = new ethers.JsonRpcProvider(
  `https://eth-mainnet.g.alchemy.com/v2/${ALCHEMY_API_KEY}`
);

// Uniswap V3 Swap event signature
const SWAP_EVENT_TOPIC = '0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67';

// Configuration
const BLOCKS_PER_DAY = 7200; // ~12 sec per block = 7200 blocks/day
const DAYS_TO_FETCH = 30;
const TOTAL_BLOCKS = BLOCKS_PER_DAY * DAYS_TO_FETCH; // 216,000 blocks
const BATCH_SIZE = 2000; // Blocks per batch (avoid rate limits)
const DELAY_MS = 1000; // 1 second delay between batches

// Output directory
const OUTPUT_DIR = path.join(__dirname, 'static');
if (!fs.existsSync(OUTPUT_DIR)) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

/**
 * Sleep utility
 */
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Get block range for N days back
 */
async function getBlockRange(daysBack) {
  console.log(`\n📅 Calculating block range for ${daysBack} days back...`);

  const currentBlock = await provider.getBlockNumber();
  const blocksBack = BLOCKS_PER_DAY * daysBack;
  const startBlock = currentBlock - blocksBack;

  console.log(`Current block: ${currentBlock}`);
  console.log(`Start block: ${startBlock}`);
  console.log(`Total blocks to fetch: ${blocksBack}`);

  return { startBlock, endBlock: currentBlock, totalBlocks: blocksBack };
}

/**
 * Fetch swap events for a block range
 */
async function fetchSwapEvents(fromBlock, toBlock, batchNumber, totalBatches) {
  try {
    const logs = await provider.getLogs({
      fromBlock,
      toBlock,
      topics: [SWAP_EVENT_TOPIC]
    });

    console.log(`  ✓ Batch ${batchNumber}/${totalBatches}: Blocks ${fromBlock}-${toBlock} → ${logs.length} swaps`);
    return logs;
  } catch (error) {
    console.error(`  ✗ Error fetching blocks ${fromBlock}-${toBlock}:`, error.message);

    // Retry with smaller range if failed
    if (toBlock - fromBlock > 500) {
      console.log(`  ⟳ Retrying with smaller batch...`);
      const midBlock = Math.floor((fromBlock + toBlock) / 2);
      const logs1 = await fetchSwapEvents(fromBlock, midBlock, batchNumber, totalBatches);
      await sleep(DELAY_MS);
      const logs2 = await fetchSwapEvents(midBlock + 1, toBlock, batchNumber, totalBatches);
      return [...logs1, ...logs2];
    }

    return [];
  }
}

/**
 * Fetch all historical data in batches
 */
async function fetchHistoricalData(startBlock, endBlock) {
  const totalBlocks = endBlock - startBlock;
  const totalBatches = Math.ceil(totalBlocks / BATCH_SIZE);

  console.log(`\n🔄 Starting data collection...`);
  console.log(`Total batches: ${totalBatches}`);
  console.log(`Estimated time: ~${Math.ceil(totalBatches * DELAY_MS / 1000 / 60)} minutes\n`);

  const allLogs = [];
  let currentBlock = startBlock;
  let batchNumber = 0;

  while (currentBlock <= endBlock) {
    batchNumber++;
    const batchEnd = Math.min(currentBlock + BATCH_SIZE - 1, endBlock);

    const logs = await fetchSwapEvents(currentBlock, batchEnd, batchNumber, totalBatches);
    allLogs.push(...logs);

    // Progress update every 10 batches
    if (batchNumber % 10 === 0) {
      const progress = (batchNumber / totalBatches * 100).toFixed(1);
      console.log(`\n📊 Progress: ${progress}% | Total swaps collected: ${allLogs.length}\n`);
    }

    currentBlock = batchEnd + 1;

    // Rate limit protection
    if (currentBlock <= endBlock) {
      await sleep(DELAY_MS);
    }
  }

  return allLogs;
}

/**
 * Get block timestamp
 */
async function getBlockTimestamp(blockNumber) {
  const block = await provider.getBlock(blockNumber);
  return block.timestamp;
}

/**
 * Parse swap log to readable format
 */
async function parseSwapLog(log) {
  const iface = new ethers.Interface([
    'event Swap(address indexed sender, address indexed recipient, int256 amount0, int256 amount1, uint160 sqrtPriceX96, uint128 liquidity, int24 tick)'
  ]);

  const parsed = iface.parseLog({
    topics: log.topics,
    data: log.data
  });

  return {
    blockNumber: log.blockNumber,
    txHash: log.transactionHash,
    poolAddress: log.address,
    sender: parsed.args.sender,
    recipient: parsed.args.recipient,
    amount0: parsed.args.amount0.toString(),
    amount1: parsed.args.amount1.toString(),
    sqrtPriceX96: parsed.args.sqrtPriceX96.toString(),
    liquidity: parsed.args.liquidity.toString(),
    tick: parsed.args.tick.toString()
  };
}

/**
 * Save logs to CSV
 */
async function saveToCSV(logs, filename) {
  console.log(`\n💾 Parsing and saving ${logs.length} transactions...`);

  // Get sample timestamps for dating
  const sampleBlocks = [
    logs[0]?.blockNumber,
    logs[Math.floor(logs.length / 2)]?.blockNumber,
    logs[logs.length - 1]?.blockNumber
  ].filter(Boolean);

  const timestamps = {};
  for (const blockNum of sampleBlocks) {
    timestamps[blockNum] = await getBlockTimestamp(blockNum);
  }

  // CSV header
  const header = 'blockNumber,timestamp,txHash,poolAddress,sender,recipient,amount0,amount1,sqrtPriceX96,liquidity,tick\n';

  // Parse logs in batches (to show progress)
  const PARSE_BATCH = 1000;
  const parsedRows = [];

  for (let i = 0; i < logs.length; i += PARSE_BATCH) {
    const batch = logs.slice(i, i + PARSE_BATCH);
    const batchParsed = await Promise.all(batch.map(parseSwapLog));
    parsedRows.push(...batchParsed);

    if (i % 10000 === 0 && i > 0) {
      console.log(`  Parsed ${i}/${logs.length} transactions...`);
    }
  }

  // Convert to CSV rows
  const rows = parsedRows.map(log => {
    // Estimate timestamp based on block number
    const nearestBlock = sampleBlocks.reduce((prev, curr) =>
      Math.abs(curr - log.blockNumber) < Math.abs(prev - log.blockNumber) ? curr : prev
    );
    const estimatedTimestamp = timestamps[nearestBlock];

    return [
      log.blockNumber,
      new Date(estimatedTimestamp * 1000).toISOString(),
      log.txHash,
      log.poolAddress,
      log.sender,
      log.recipient,
      log.amount0,
      log.amount1,
      log.sqrtPriceX96,
      log.liquidity,
      log.tick
    ].join(',');
  });

  const csv = header + rows.join('\n');

  const filepath = path.join(OUTPUT_DIR, filename);
  fs.writeFileSync(filepath, csv);

  console.log(`✅ Saved to: ${filepath}`);
  console.log(`📊 File size: ${(fs.statSync(filepath).size / 1024 / 1024).toFixed(2)} MB`);

  return filepath;
}

/**
 * Main execution
 */
async function main() {
  console.log('╔════════════════════════════════════════════════════════════════╗');
  console.log('║                                                                ║');
  console.log('║       30-DAY HISTORICAL DATA COLLECTOR                        ║');
  console.log('║       All Pool Types (ETH + Stablecoins + Tokens)            ║');
  console.log('║                                                                ║');
  console.log('╚════════════════════════════════════════════════════════════════╝');

  try {
    // Get block range
    const { startBlock, endBlock, totalBlocks } = await getBlockRange(DAYS_TO_FETCH);

    // Fetch historical data
    console.log(`\n🚀 Fetching swap events...`);
    const startTime = Date.now();

    const logs = await fetchHistoricalData(startBlock, endBlock);

    const elapsedMin = ((Date.now() - startTime) / 1000 / 60).toFixed(1);

    console.log(`\n✅ Collection complete!`);
    console.log(`   Total transactions: ${logs.length.toLocaleString()}`);
    console.log(`   Time elapsed: ${elapsedMin} minutes`);

    // Save to CSV
    const filename = `pool_logs_30d_${new Date().toISOString().split('T')[0]}.csv`;
    await saveToCSV(logs, filename);

    // Summary stats
    const uniquePools = new Set(logs.map(log => log.address)).size;
    console.log(`\n📈 Summary:`);
    console.log(`   Unique pools: ${uniquePools.toLocaleString()}`);
    console.log(`   Avg transactions per pool: ${Math.round(logs.length / uniquePools)}`);

    console.log(`\n🎉 Phase 1 Complete! Ready for Phase 2 (Pool Classification)`);

  } catch (error) {
    console.error('\n❌ Error:', error);
    process.exit(1);
  }
}

// Run if called directly
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main();
}

export { getBlockRange, fetchHistoricalData, saveToCSV };
