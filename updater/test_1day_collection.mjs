/**
 * Test 1-Day Collection - Verify setup before full 30-day run
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
dotenv.config({ path: path.join(__dirname, 'updater/.env') });

const ALCHEMY_API_KEY = process.env.ALCHEMY_API_KEY;
if (!ALCHEMY_API_KEY) {
  console.error('❌ ALCHEMY_API_KEY not found!');
  console.log('Please set it in .env file');
  process.exit(1);
}

const provider = new ethers.JsonRpcProvider(
  `https://eth-mainnet.g.alchemy.com/v2/${ALCHEMY_API_KEY}`
);

const SWAP_EVENT_TOPIC = '0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67';
const BLOCKS_PER_DAY = 7200;

console.log('╔════════════════════════════════════════════════════════════════╗');
console.log('║           1-DAY TEST COLLECTION                               ║');
console.log('╚════════════════════════════════════════════════════════════════╝\n');

async function testCollection() {
  try {
    // Get current block
    console.log('📡 Connecting to Ethereum...');
    const currentBlock = await provider.getBlockNumber();
    const startBlock = currentBlock - BLOCKS_PER_DAY;

    console.log(`✅ Connected!`);
    console.log(`   Current block: ${currentBlock}`);
    console.log(`   Start block: ${startBlock} (24 hours ago)`);
    console.log(`   Range: ${BLOCKS_PER_DAY} blocks\n`);

    // Fetch logs
    console.log('🔄 Fetching swap events (this may take 30-60 seconds)...\n');
    const logs = await provider.getLogs({
      fromBlock: startBlock,
      toBlock: currentBlock,
      topics: [SWAP_EVENT_TOPIC]
    });

    console.log(`✅ Collection successful!`);
    console.log(`   Total transactions: ${logs.length.toLocaleString()}`);

    // Analyze pools
    const poolCounts = {};
    logs.forEach(log => {
      poolCounts[log.address] = (poolCounts[log.address] || 0) + 1;
    });

    const uniquePools = Object.keys(poolCounts).length;
    const topPools = Object.entries(poolCounts)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 5);

    console.log(`   Unique pools: ${uniquePools.toLocaleString()}`);
    console.log(`   Avg txs per pool: ${Math.round(logs.length / uniquePools)}\n`);

    console.log('🏆 Top 5 Most Active Pools:');
    topPools.forEach(([address, count], i) => {
      console.log(`   ${i + 1}. ${address.slice(0, 10)}... - ${count} transactions`);
    });

    console.log('\n✅ Test successful! Ready to run 30-day collection.');
    console.log('\nTo run full collection:');
    console.log('  cd updater && node historical_collector.mjs');

  } catch (error) {
    console.error('\n❌ Error:', error.message);
    if (error.message.includes('rate limit')) {
      console.log('\n💡 Tip: Wait a minute and try again');
    }
    process.exit(1);
  }
}

testCollection();
