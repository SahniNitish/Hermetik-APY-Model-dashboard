/**
 * STABLECOIN HISTORICAL DATA FETCHER (March 2 - June 1, 2025)
 * ============================================================
 * Fetches transaction data for stablecoin pools only from March 2 to June 1, 2025
 * Optimized for our 27-stablecoin universe
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

// Our 27 stablecoins (lowercase for comparison)
const STABLECOINS = new Set([
  '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48', // USDC
  '0xdac17f958d2ee523a2206206994597c13d831ec7', // USDT
  '0x6b175474e89094c44da98b954eedeac495271d0f', // DAI
  '0x853d955acef822db058eb8505911ed77f175b99e', // FRAX
  '0x5f98805a4e8be255a32880fdec7f6728c6568ba0', // LUSD
  '0x4fabb145d64652a948d72533023f6e7a623c7c53', // BUSD
  '0x0000000000085d4780b73119b644ae5ecd22b376', // TUSD
  '0x056fd409e1d7a124bd7017459dfea2f387b6d5cd', // GUSD
  '0x6c3ea9036406852006290770bedfcaba0e23a0e8', // PYUSD
  '0x4c9edd5852cd905f086c759e8383e09bff1e68b3', // USDE
  '0x40d16fc0246ad3160ccc09b8d0d3a2cd28ae6c2f', // GHO
  '0x9d39a5de30e57443bff2a8307a4256c8797a3497', // SUSDE
  '0xdc035d45d973e3ec169d2276ddab16f1e407384f', // USDS
  '0xa3931d71877c0e7a3148cb7eb4463524fec27fbd', // SUSDS
  '0xcacd6fd266af91b8aed52accc382b4e165586e29', // FRXUSD
  '0x3175df0976dfa876431c2e9ee6bc45b65d3473cc', // FRAXBP
  '0x8292bb45bf1ee4d140127049757c2e0ff06317ed', // RLUSD
  '0x80ac24aa929eaf5013f6436cda2a7ba190f5cc0b', // SYRUPUSDC
  '0xe2f2a5c287993345a840db3b0845fbc70f5935a5', // MUSD
  '0xa693b19d2931d498c5b318df961919bb4aee87a5', // UST
  '0x4e3fbd56cd56c3e72c1403e103b45db9da5b9d2b', // CVX
  '0x0cec1a9154ff802e7934fc916ed7ca50bde6844e', // POOL
  '0x9f8f72aa9304c8b593d555f12ef6589cc3a579a2', // MKR
  '0x1985365e9f78359a9b6ad760e32412f4a445e862', // REP
  '0xa8b50c4a55aaebfe34b56a87cf1bab4a1e9b1ab4', // EURT
  '0x1456688345527be1f37e9e627da0837d6f08c925', // EURS
  '0xf1d50c3c0694710c2b9bf2b34d5c1dce4a7e3a51'  // EUROC
]);

// Uniswap V3 Factory address
const UNISWAP_V3_FACTORY = '0x1F98431c8aD98523631AE4a59f267346ea31F984';

// Pool Creation event topic
const POOL_CREATION_TOPIC = '0x783cca1c0412dd0d695e784568c96da2e9c22ff989357a2e8b1d9b2b4e6b7118';

// Known stablecoin pools (from our data)
const KNOWN_STABLECOIN_POOLS = new Set([
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
  '0x5c95d4b1c3321cf898d25949f41d50be2db5bc1d',
  // Add more as discovered
]);

/**
 * Get the date range for fetching (March 2 - June 1, 2025)
 */
function getDateRange() {
  const startDate = new Date('2025-03-02T00:00:00Z');
  const endDate = new Date('2025-06-01T23:59:59Z');
  return { startDate, endDate };
}

/**
 * Convert date to block number (approximate)
 */
async function dateToBlockNumber(targetDate) {
  // Ethereum average block time is ~12 seconds
  const SECONDS_PER_BLOCK = 12;
  
  // Get current block and timestamp
  const currentBlock = await provider.getBlockNumber();
  const currentBlockData = await provider.getBlock(currentBlock);
  const currentTimestamp = currentBlockData.timestamp;
  
  // Calculate blocks difference
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
    console.log(`    📍 Fetching ${poolAddress} for ${date}...`);
    
    // Get all transactions in the block range for this pool
    const swapEventSignature = '0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67';
    
    const logs = await provider.getLogs({
      fromBlock: blockRange.start,
      toBlock: blockRange.end,
      address: poolAddress,
      topics: [swapEventSignature]
    });
    
    console.log(`      Found ${logs.length} transactions`);
    
    // Process transactions
    const transactions = [];
    for (const log of logs) {
      try {
        const block = await provider.getBlock(log.blockNumber);
        transactions.push({
          blockNumber: log.blockNumber,
          transactionHash: log.transactionHash,
          poolAddress: poolAddress.toLowerCase(),
          date: date
        });
      } catch (error) {
        console.error(`      ⚠️  Error processing tx ${log.transactionHash}:`, error.message);
      }
    }
    
    return transactions;
  } catch (error) {
    console.error(`    ❌ Error fetching pool ${poolAddress}:`, error.message);
    return [];
  }
}

/**
 * Discover additional stablecoin pools
 */
async function discoverStablecoinPools(blockRange) {
  console.log('  🔍 Discovering stablecoin pools...');
  
  try {
    // Get pool creation events in the date range
    const logs = await provider.getLogs({
      fromBlock: Math.max(1, blockRange.start - 1000000), // Look back for pool creation
      toBlock: blockRange.end,
      address: UNISWAP_V3_FACTORY,
      topics: [POOL_CREATION_TOPIC]
    });
    
    console.log(`    Found ${logs.length} pool creation events to analyze`);
    
    const discoveredPools = new Set(KNOWN_STABLECOIN_POOLS);
    
    for (const log of logs) {
      try {
        // Decode the pool creation event
        const decoded = ethers.AbiCoder.defaultAbiCoder().decode(
          ['address', 'address', 'uint24', 'int24', 'address'],
          log.data
        );
        
        const token0 = decoded[0].toLowerCase();
        const token1 = decoded[1].toLowerCase();
        const fee = decoded[2];
        const poolAddress = decoded[4].toLowerCase();
        
        // Check if both tokens are stablecoins
        if (STABLECOINS.has(token0) && STABLECOINS.has(token1)) {
          console.log(`    ✨ Discovered stablecoin pool: ${poolAddress} (${token0}/${token1}, fee: ${fee})`);
          discoveredPools.add(poolAddress);
        }
      } catch (error) {
        // Skip malformed events
      }
    }
    
    console.log(`    📊 Total stablecoin pools: ${discoveredPools.size}`);
    return Array.from(discoveredPools);
    
  } catch (error) {
    console.error('  ❌ Error discovering pools:', error.message);
    return Array.from(KNOWN_STABLECOIN_POOLS);
  }
}

/**
 * Process a single date
 */
async function processDate(date, pools) {
  const dateStr = date.toISOString().split('T')[0];
  console.log(`\n📅 Processing ${dateStr}...`);
  
  try {
    // Calculate block range for this date
    const startOfDay = new Date(date);
    startOfDay.setUTCHours(0, 0, 0, 0);
    
    const endOfDay = new Date(date);
    endOfDay.setUTCHours(23, 59, 59, 999);
    
    const startBlock = await dateToBlockNumber(startOfDay);
    const endBlock = await dateToBlockNumber(endOfDay);
    
    console.log(`  🔗 Block range: ${startBlock} to ${endBlock}`);
    
    const blockRange = { start: startBlock, end: endBlock };
    
    // Collect all transactions for this date
    const allTransactions = [];
    
    // Process pools in batches to avoid rate limits
    const BATCH_SIZE = 5;
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
      if (i + BATCH_SIZE < pools.length) {
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
    }
    
    console.log(`  📊 Total transactions found: ${allTransactions.length}`);
    
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
    } else {
      console.log(`  ⚠️  No transactions found for ${dateStr}`);
    }
    
    return allTransactions.length;
    
  } catch (error) {
    console.error(`  ❌ Error processing ${dateStr}:`, error.message);
    return 0;
  }
}

/**
 * Main execution
 */
async function main() {
  console.log('=' .repeat(80));
  console.log('STABLECOIN DATA FETCHER: March 2 - June 1, 2025');
  console.log('=' .repeat(80));
  
  try {
    const { startDate, endDate } = getDateRange();
    console.log(`📊 Fetching data from ${startDate.toISOString().split('T')[0]} to ${endDate.toISOString().split('T')[0]}`);
    
    // Create static directory if it doesn't exist
    const staticDir = path.join(__dirname, 'static');
    if (!fs.existsSync(staticDir)) {
      fs.mkdirSync(staticDir, { recursive: true });
    }
    
    // Discover stablecoin pools
    const sampleBlockRange = {
      start: await dateToBlockNumber(startDate),
      end: await dateToBlockNumber(endDate)
    };
    
    const pools = await discoverStablecoinPools(sampleBlockRange);
    console.log(`\n🏊 Processing ${pools.length} stablecoin pools`);
    
    // Process each date
    let totalTransactions = 0;
    const currentDate = new Date(startDate);
    
    while (currentDate <= endDate) {
      const txCount = await processDate(currentDate, pools);
      totalTransactions += txCount;
      
      // Move to next day
      currentDate.setUTCDate(currentDate.getUTCDate() + 1);
      
      // Rate limiting between days
      await new Promise(resolve => setTimeout(resolve, 2000));
    }
    
    console.log('\n' + '=' .repeat(80));
    console.log('✅ STABLECOIN DATA COLLECTION COMPLETE!');
    console.log('=' .repeat(80));
    console.log(`📊 Total transactions collected: ${totalTransactions.toLocaleString()}`);
    console.log(`📁 Files saved in: ${staticDir}`);
    console.log('\n🎯 Ready for data processing and analysis!');
    
  } catch (error) {
    console.error('❌ Fatal error:', error);
    process.exit(1);
  }
}

// Run the fetcher
main().catch(console.error);