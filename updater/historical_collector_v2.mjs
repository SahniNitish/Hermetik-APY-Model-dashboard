/**
 * Historical Data Collector V2 - Memory-Efficient Version
 * Processes and saves data in batches to avoid memory issues
 */

import { ethers } from 'ethers';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import dotenv from 'dotenv';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

dotenv.config({ path: path.join(__dirname, '.env') });

const ALCHEMY_API_KEY = process.env.ALCHEMY_API_KEY;
if (!ALCHEMY_API_KEY) {
  throw new Error('ALCHEMY_API_KEY not found in .env file');
}

const provider = new ethers.JsonRpcProvider(
  `https://eth-mainnet.g.alchemy.com/v2/${ALCHEMY_API_KEY}`
);

const SWAP_EVENT_TOPIC = '0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67';

// Configuration
const BLOCKS_PER_DAY = 7200;
const DAYS_TO_FETCH = 30;
const BATCH_SIZE = 1000; // Smaller batches for memory efficiency
const DELAY_MS = 800;

const OUTPUT_DIR = path.join(__dirname, 'static');
if (!fs.existsSync(OUTPUT_DIR)) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Parse swap log - simplified for memory efficiency
 */
function parseSwapLogSimple(log, timestamp) {
  try {
    const iface = new ethers.Interface([
      'event Swap(address indexed sender, address indexed recipient, int256 amount0, int256 amount1, uint160 sqrtPriceX96, uint128 liquidity, int24 tick)'
    ]);

    const parsed = iface.parseLog({
      topics: log.topics,
      data: log.data
    });

    return [
      log.blockNumber,
      timestamp,
      log.transactionHash,
      log.address.toLowerCase(),
      parsed.args.sender.toLowerCase(),
      parsed.args.recipient.toLowerCase(),
      parsed.args.amount0.toString(),
      parsed.args.amount1.toString(),
      parsed.args.sqrtPriceX96.toString(),
      parsed.args.liquidity.toString(),
      parsed.args.tick.toString()
    ].join(',');

  } catch (error) {
    return null;
  }
}

/**
 * Fetch and save batch
 */
async function fetchAndSaveBatch(fromBlock, toBlock, fileHandle, batchNum, totalBatches) {
  try {
    // Get logs
    const logs = await provider.getLogs({
      fromBlock,
      toBlock,
      topics: [SWAP_EVENT_TOPIC]
    });

    if (logs.length === 0) {
      console.log(`  Batch ${batchNum}/${totalBatches}: Blocks ${fromBlock}-${toBlock} → 0 swaps (skipped)`);
      return 0;
    }

    // Get block timestamp (sample from middle)
    const midBlock = Math.floor((fromBlock + toBlock) / 2);
    const block = await provider.getBlock(midBlock);
    const timestamp = new Date(block.timestamp * 1000).toISOString();

    // Parse and write immediately
    let validLogs = 0;
    for (const log of logs) {
      const csvRow = parseSwapLogSimple(log, timestamp);
      if (csvRow) {
        fs.appendFileSync(fileHandle, csvRow + '\n');
        validLogs++;
      }
    }

    console.log(`  ✓ Batch ${batchNum}/${totalBatches}: Blocks ${fromBlock}-${toBlock} → ${validLogs} swaps saved`);

    return validLogs;

  } catch (error) {
    console.error(`  ✗ Error in batch ${batchNum}:`, error.message);

    // Retry with smaller range
    if (toBlock - fromBlock > 200) {
      const midBlock = Math.floor((fromBlock + toBlock) / 2);
      const count1 = await fetchAndSaveBatch(fromBlock, midBlock, fileHandle, batchNum, totalBatches);
      await sleep(DELAY_MS);
      const count2 = await fetchAndSaveBatch(midBlock + 1, toBlock, fileHandle, batchNum, totalBatches);
      return count1 + count2;
    }

    return 0;
  }
}

/**
 * Main collection function
 */
async function collectHistoricalData(daysBack = DAYS_TO_FETCH) {
  console.log('╔════════════════════════════════════════════════════════════════╗');
  console.log('║                                                                ║');
  console.log('║       30-DAY HISTORICAL DATA COLLECTOR (Memory Optimized)     ║');
  console.log('║       All Pool Types - Batch Processing                      ║');
  console.log('║                                                                ║');
  console.log('╚════════════════════════════════════════════════════════════════╝\n');

  try {
    // Get block range
    console.log('📡 Connecting to Ethereum...');
    const currentBlock = await provider.getBlockNumber();
    const blocksBack = BLOCKS_PER_DAY * daysBack;
    const startBlock = currentBlock - blocksBack;

    console.log(`✅ Connected!`);
    console.log(`   Current block: ${currentBlock}`);
    console.log(`   Start block: ${startBlock} (${daysBack} days ago)`);
    console.log(`   Total blocks: ${blocksBack}\n`);

    const totalBatches = Math.ceil(blocksBack / BATCH_SIZE);
    console.log(`📊 Collection Plan:`);
    console.log(`   Batch size: ${BATCH_SIZE} blocks`);
    console.log(`   Total batches: ${totalBatches}`);
    console.log(`   Estimated time: ~${Math.ceil(totalBatches * DELAY_MS / 1000 / 60)} minutes\n`);

    // Create output file
    const filename = `pool_logs_${daysBack}d_${new Date().toISOString().split('T')[0]}.csv`;
    const filepath = path.join(OUTPUT_DIR, filename);

    // Write header
    const header = 'blockNumber,timestamp,txHash,poolAddress,sender,recipient,amount0,amount1,sqrtPriceX96,liquidity,tick\n';
    fs.writeFileSync(filepath, header);

    console.log(`💾 Saving to: ${filename}\n`);
    console.log('🔄 Starting collection...\n');

    // Fetch in batches
    let currentBlockNum = startBlock;
    let batchNum = 0;
    let totalSwaps = 0;
    const startTime = Date.now();

    while (currentBlockNum <= currentBlock) {
      batchNum++;
      const batchEnd = Math.min(currentBlockNum + BATCH_SIZE - 1, currentBlock);

      const swapCount = await fetchAndSaveBatch(
        currentBlockNum,
        batchEnd,
        filepath,
        batchNum,
        totalBatches
      );

      totalSwaps += swapCount;

      // Progress update every 20 batches
      if (batchNum % 20 === 0) {
        const progress = (batchNum / totalBatches * 100).toFixed(1);
        const elapsedMin = ((Date.now() - startTime) / 1000 / 60).toFixed(1);
        const fileSize = (fs.statSync(filepath).size / 1024 / 1024).toFixed(2);
        console.log(`\n📈 Progress: ${progress}% | Swaps: ${totalSwaps.toLocaleString()} | Time: ${elapsedMin}m | Size: ${fileSize}MB\n`);
      }

      currentBlockNum = batchEnd + 1;

      // Rate limit protection
      if (currentBlockNum <= currentBlock) {
        await sleep(DELAY_MS);
      }
    }

    // Final summary
    const totalTime = ((Date.now() - startTime) / 1000 / 60).toFixed(1);
    const fileSize = (fs.statSync(filepath).size / 1024 / 1024).toFixed(2);
    const uniquePools = new Set();

    // Count unique pools from file
    console.log('\n📊 Analyzing unique pools...');
    const data = fs.readFileSync(filepath, 'utf8');
    const lines = data.split('\n').slice(1); // Skip header
    lines.forEach(line => {
      const parts = line.split(',');
      if (parts.length > 3) {
        uniquePools.add(parts[3]); // poolAddress column
      }
    });

    console.log('\n╔════════════════════════════════════════════════════════════════╗');
    console.log('║                    COLLECTION COMPLETE!                       ║');
    console.log('╚════════════════════════════════════════════════════════════════╝\n');

    console.log(`✅ Results:`);
    console.log(`   Total transactions: ${totalSwaps.toLocaleString()}`);
    console.log(`   Unique pools: ${uniquePools.size.toLocaleString()}`);
    console.log(`   Time elapsed: ${totalTime} minutes`);
    console.log(`   File size: ${fileSize} MB`);
    console.log(`   Output file: ${filepath}\n`);

    console.log(`🎉 Phase 1 Complete!`);
    console.log(`\nNext: Run Phase 2 (Pool Classification)\n`);

    return filepath;

  } catch (error) {
    console.error('\n❌ Error:', error);
    throw error;
  }
}

// Run if called directly
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const daysArg = process.argv[2];
  const days = daysArg ? parseInt(daysArg) : DAYS_TO_FETCH;

  collectHistoricalData(days)
    .then(() => process.exit(0))
    .catch(error => {
      console.error(error);
      process.exit(1);
    });
}

export { collectHistoricalData };
