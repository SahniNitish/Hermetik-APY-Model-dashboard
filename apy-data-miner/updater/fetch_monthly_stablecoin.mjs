/**
 * MONTHLY STABLECOIN DATA FETCHER
 * ===============================
 * Fetches stablecoin transaction data one month at a time
 * Usage: node fetch_monthly_stablecoin.mjs [YYYY-MM]
 * Example: node fetch_monthly_stablecoin.mjs 2025-03
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

const provider = new ethers.JsonRpcProvider(
  `https://eth-mainnet.g.alchemy.com/v2/${ALCHEMY_API_KEY}`
);

// Known stablecoin pools from our data
const KNOWN_STABLECOIN_POOLS = [
  '0x00cef0386ed94d738c8f8a74e8bfd0376926d24c',
  '0x13394005c1012e708fce1eb974f1130fdc73a5ce', 
  '0x16980c16811bde2b3358c1ce4341541a4c772ec9',
  '0x2bc477c7c00511ec8a2ea667dd8210af9ff15e1d',
  '0x3416cf6c708da44db2624d63ea0aaef7113527c6',
  '0x435664008f38b0650fbc1c9fc971d0a3bc2f1e47',
  '0x48c0f5e663d682a6450995f210fd1ef8abad7a61',
  '0x48da0965ab2d2cbf1c17c09cfb5cbe67ad5b1406',
  '0x4e0924d3a751be199c426d52fb1f2337fa96f736',
  '0x5777d92f208679db4b9778590fa3cab3ac9e2168',
  '0x58b8a1cae4c8eede897c0c9987ff4b5714ef3975',
  '0x5aa1356999821b533ec5d9f79c23b8cb7c295c61',
  '0x5c95d4b1c3321cf898d25949f41d50be2db5bc1d'
];

/**
 * Convert date to block number (approximate)
 */
async function dateToBlockNumber(targetDate) {
  const SECONDS_PER_BLOCK = 12;
  
  const currentBlock = await provider.getBlockNumber();
  const currentBlockData = await provider.getBlock(currentBlock);
  const currentTimestamp = currentBlockData.timestamp;
  
  const targetTimestamp = Math.floor(targetDate.getTime() / 1000);
  const timeDiff = targetTimestamp - currentTimestamp;
  const blocksDiff = Math.floor(timeDiff / SECONDS_PER_BLOCK);
  
  return currentBlock + blocksDiff;
}

/**
 * Get transactions for a specific pool on a specific date
 */
async function getPoolTransactions(poolAddress, date, blockRange) {
  try {
    const swapEventSignature = '0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67';
    
    const logs = await provider.getLogs({
      fromBlock: blockRange.start,
      toBlock: blockRange.end,
      address: poolAddress,
      topics: [swapEventSignature]
    });
    
    const transactions = logs.map(log => ({
      blockNumber: log.blockNumber,
      transactionHash: log.transactionHash,
      poolAddress: poolAddress.toLowerCase(),
      date: date
    }));
    
    return transactions;
  } catch (error) {
    console.error(`    ❌ Error fetching pool ${poolAddress}:`, error.message);
    return [];
  }
}

/**
 * Process a single date
 */
async function processDate(date, pools) {
  const dateStr = date.toISOString().split('T')[0];
  console.log(`📅 Processing ${dateStr}...`);
  
  try {
    // Calculate block range for this date
    const startOfDay = new Date(date);
    startOfDay.setUTCHours(0, 0, 0, 0);
    
    const endOfDay = new Date(date);
    endOfDay.setUTCHours(23, 59, 59, 999);
    
    const startBlock = await dateToBlockNumber(startOfDay);
    const endBlock = await dateToBlockNumber(endOfDay);
    
    const blockRange = { start: startBlock, end: endBlock };
    
    // Collect all transactions for this date
    const allTransactions = [];
    
    // Process pools in smaller batches
    const BATCH_SIZE = 3;
    for (let i = 0; i < pools.length; i += BATCH_SIZE) {
      const batch = pools.slice(i, i + BATCH_SIZE);
      
      const batchPromises = batch.map(pool => 
        getPoolTransactions(pool, dateStr, blockRange)
      );
      
      const batchResults = await Promise.all(batchPromises);
      
      for (const transactions of batchResults) {
        allTransactions.push(...transactions);
      }
      
      // Rate limiting
      await new Promise(resolve => setTimeout(resolve, 500));
    }
    
    console.log(`  📊 Found ${allTransactions.length} transactions`);
    
    // Save to file
    if (allTransactions.length > 0) {
      const filename = path.join(__dirname, 'static', `stablecoin_txs_${dateStr}.csv`);
      
      const csvContent = [
        'blockNumber,transactionHash,poolAddress,date',
        ...allTransactions.map(tx => 
          `${tx.blockNumber},${tx.transactionHash},${tx.poolAddress},${tx.date}`
        )
      ].join('\n');
      
      fs.writeFileSync(filename, csvContent);
      console.log(`  ✅ Saved: ${filename}`);
    }
    
    return allTransactions.length;
  } catch (error) {
    console.error(`  ❌ Error processing ${dateStr}:`, error.message);
    return 0;
  }
}

/**
 * Get month range
 */
function getMonthRange(yearMonth) {
  const [year, month] = yearMonth.split('-').map(Number);
  const startDate = new Date(year, month - 1, 1);
  const endDate = new Date(year, month, 0); // Last day of month
  
  return { startDate, endDate };
}

/**
 * Main execution
 */
async function main() {
  const yearMonth = process.argv[2];
  
  if (!yearMonth || !/^\d{4}-\d{2}$/.test(yearMonth)) {
    console.error('Usage: node fetch_monthly_stablecoin.mjs [YYYY-MM]');
    console.error('Example: node fetch_monthly_stablecoin.mjs 2025-03');
    process.exit(1);
  }
  
  console.log('=' .repeat(80));
  console.log(`MONTHLY STABLECOIN DATA FETCHER: ${yearMonth}`);
  console.log('=' .repeat(80));
  
  try {
    const { startDate, endDate } = getMonthRange(yearMonth);
    console.log(`📊 Fetching data for ${yearMonth} (${startDate.toISOString().split('T')[0]} to ${endDate.toISOString().split('T')[0]})`);
    
    // Create static directory if it doesn't exist
    const staticDir = path.join(__dirname, 'static');
    if (!fs.existsSync(staticDir)) {
      fs.mkdirSync(staticDir, { recursive: true });
    }
    
    console.log(`\n🏊 Processing ${KNOWN_STABLECOIN_POOLS.length} stablecoin pools`);
    
    // Process each date
    let totalTransactions = 0;
    const currentDate = new Date(startDate);
    
    while (currentDate <= endDate) {
      const txCount = await processDate(currentDate, KNOWN_STABLECOIN_POOLS);
      totalTransactions += txCount;
      
      // Move to next day
      currentDate.setUTCDate(currentDate.getUTCDate() + 1);
      
      // Rate limiting between days
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
    
    console.log('\n' + '=' .repeat(80));
    console.log(`✅ ${yearMonth} DATA COLLECTION COMPLETE!`);
    console.log('=' .repeat(80));
    console.log(`📊 Total transactions collected: ${totalTransactions.toLocaleString()}`);
    console.log(`📁 Files saved in: ${staticDir}`);
    
  } catch (error) {
    console.error('❌ Fatal error:', error);
    process.exit(1);
  }
}

main().catch(console.error);