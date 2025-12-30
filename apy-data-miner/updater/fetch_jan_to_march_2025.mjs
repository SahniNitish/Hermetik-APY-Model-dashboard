/**
 * STABLECOIN DATA FETCHER (January 1 - March 1, 2025)
 * ===================================================
 * Efficiently fetches stablecoin transaction data for the specified date range
 * Builds upon existing January data
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

// Our 27 stablecoins
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
  '0x8e870d67f660d95d5be530380d0ec0bd388289e1', // USDP
  '0x1abaea1f7c830bd89acc67ec4af516284b1bc33c', // EUROC
  '0xc581b735a1688071a1746c968e0798d642ede491', // EURT
  '0x0c10bf8fcb7bf5412187a595ab97a3609160b5c6', // USDD
  '0xa47c8bf37f92abed4a126bda807a7b7498661acd', // USTC
  '0xad3e3fc59dff318beceaab7d00eb4f68b1ecf195', // WCUSD
  '0x2a8e1e676ec238d8a992307b495b45b3feaa5e86'  // OUSD
]);

let STABLECOIN_POOLS = new Set();

// Generate specific dates from Jan 5 to Mar 1
function generateTargetDates() {
  const dates = [];
  
  // January 5-31
  for (let day = 5; day <= 31; day++) {
    dates.push(`2025-01-${day.toString().padStart(2, '0')}`);
  }
  
  // February 1-28
  for (let day = 1; day <= 28; day++) {
    dates.push(`2025-02-${day.toString().padStart(2, '0')}`);
  }
  
  // March 1
  dates.push('2025-03-01');
  
  return dates;
}

const TARGET_DATES = generateTargetDates();

// Uniswap V3 Swap event signature
const SWAP_EVENT_TOPIC = '0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67';

// Configuration
const BLOCKS_PER_DAY = 7200;
const BATCH_SIZE = 2000;
const DELAY_MS = 1000;

/**
 * Get block number for a specific date
 */
async function getBlockByDate(targetDate) {
  console.log(`🔍 Finding block number for ${targetDate}...`);
  
  const targetTimestamp = Math.floor(new Date(targetDate + 'T00:00:00Z').getTime() / 1000);
  let left = 21500000; 
  let right = await provider.getBlockNumber();
  
  while (left < right) {
    const mid = Math.floor((left + right) / 2);
    const block = await provider.getBlock(mid);
    
    if (block.timestamp < targetTimestamp) {
      left = mid + 1;
    } else {
      right = mid;
    }
  }
  
  const finalBlock = await provider.getBlock(left);
  const actualDate = new Date(finalBlock.timestamp * 1000).toISOString().split('T')[0];
  
  console.log(`✅ Block ${left} (${actualDate})`);
  return left;
}

/**
 * Load stablecoin pool addresses from metadata
 */
function loadStablecoinPools() {
  try {
    const metadataPath = path.join(__dirname, 'static', 'pool_metadata.csv');
    if (!fs.existsSync(metadataPath)) {
      throw new Error('pool_metadata.csv not found! Run pool classifier first.');
    }
    
    const csvData = fs.readFileSync(metadataPath, 'utf8');
    const lines = csvData.split('\n').slice(1);
    
    let stablecoinCount = 0;
    
    for (const line of lines) {
      if (!line.trim()) continue;
      
      const [poolAddress, , , , , , poolType] = line.split(',');
      
      if (poolType && poolType.trim() === 'stablecoin') {
        STABLECOIN_POOLS.add(poolAddress.toLowerCase());
        stablecoinCount++;
      }
    }
    
    console.log(`📊 Loaded ${stablecoinCount} stablecoin pools from metadata`);
    return stablecoinCount > 0;
    
  } catch (error) {
    console.error(`❌ Error loading pool metadata: ${error.message}`);
    return false;
  }
}

/**
 * Check if a pool contains only stablecoins
 */
async function isStablecoinPool(poolAddress) {
  if (STABLECOIN_POOLS.has(poolAddress.toLowerCase())) {
    return true;
  }
  return false;
}

/**
 * Check if file already exists
 */
function fileExists(filename) {
  const filePath = path.join(__dirname, 'static', filename);
  return fs.existsSync(filePath);
}

/**
 * Fetch transactions for a specific day
 */
async function fetchStablecoinDataForDay(targetDate, blockNumber) {
  const filename = `stablecoin_txs_${targetDate}.csv`;
  
  if (fileExists(filename)) {
    console.log(`⏭️  Skipping ${targetDate} - file already exists`);
    return [];
  }
  
  console.log(`\n📅 Fetching stablecoin data for ${targetDate}...`);
  
  const fromBlock = blockNumber;
  const toBlock = blockNumber + BLOCKS_PER_DAY;
  
  const allTransactions = [];
  let totalBatches = Math.ceil(BLOCKS_PER_DAY / BATCH_SIZE);
  let processedBatches = 0;
  
  for (let currentBlock = fromBlock; currentBlock < toBlock; currentBlock += BATCH_SIZE) {
    const batchEnd = Math.min(currentBlock + BATCH_SIZE - 1, toBlock - 1);
    processedBatches++;
    
    try {
      console.log(`  📦 Batch ${processedBatches}/${totalBatches} (blocks ${currentBlock}-${batchEnd})`);
      
      const logs = await provider.getLogs({
        fromBlock: currentBlock,
        toBlock: batchEnd,
        topics: [SWAP_EVENT_TOPIC]
      });
      
      let stablecoinTxs = 0;
      
      for (const log of logs) {
        if (await isStablecoinPool(log.address)) {
          allTransactions.push({
            blockNumber: log.blockNumber,
            transactionHash: log.transactionHash,
            poolAddress: log.address.toLowerCase(),
            date: targetDate
          });
          stablecoinTxs++;
        }
      }
      
      console.log(`    ✅ Found ${logs.length} total swaps, ${stablecoinTxs} from stablecoin pools`);
      
      if (processedBatches < totalBatches) {
        await sleep(DELAY_MS);
      }
      
    } catch (error) {
      console.error(`    ❌ Error in batch ${processedBatches}: ${error.message}`);
      continue;
    }
  }
  
  console.log(`✅ ${targetDate}: Collected ${allTransactions.length} stablecoin transactions`);
  
  // Save the day's data immediately
  saveToCSV(allTransactions, filename);
  
  return allTransactions;
}

/**
 * Sleep utility
 */
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Save data to CSV
 */
function saveToCSV(data, filename) {
  const outputPath = path.join(__dirname, 'static', filename);
  
  if (data.length === 0) {
    console.log(`⚠️  No data to save for ${filename}`);
    return;
  }
  
  const header = 'blockNumber,transactionHash,poolAddress,date\n';
  const csvContent = header + data.map(tx => 
    `${tx.blockNumber},${tx.transactionHash},${tx.poolAddress},${tx.date}`
  ).join('\n');
  
  fs.writeFileSync(outputPath, csvContent);
  console.log(`💾 Saved ${data.length} transactions to ${filename}`);
}

/**
 * Main execution
 */
async function main() {
  console.log('================================================================================');
  console.log('STABLECOIN DATA FETCHER (January 5 - March 1, 2025)');
  console.log('================================================================================');
  
  try {
    const poolsLoaded = loadStablecoinPools();
    if (!poolsLoaded) {
      console.log('⚠️  Warning: No pool metadata found.');
      return;
    }
    
    const allTransactions = [];
    
    console.log(`🎯 Target dates: ${TARGET_DATES.length} days from Jan 5 to Mar 1, 2025`);
    
    let processedDays = 0;
    for (const targetDate of TARGET_DATES) {
      try {
        processedDays++;
        console.log(`\n[${processedDays}/${TARGET_DATES.length}] Processing ${targetDate}`);
        
        const blockNumber = await getBlockByDate(targetDate);
        const dayTransactions = await fetchStablecoinDataForDay(targetDate, blockNumber);
        allTransactions.push(...dayTransactions);
        
      } catch (error) {
        console.error(`❌ Error fetching data for ${targetDate}: ${error.message}`);
        continue;
      }
    }
    
    console.log('\n================================================================================');
    console.log('✅ STABLECOIN DATA COLLECTION COMPLETE!');
    console.log('================================================================================');
    console.log(`📊 Total transactions collected in this run: ${allTransactions.length.toLocaleString()}`);
    console.log(`📅 Date range: January 5 - March 1, 2025`);
    console.log(`🎯 Pools covered: ${STABLECOIN_POOLS.size} stablecoin pools`);
    
  } catch (error) {
    console.error(`❌ Fatal error: ${error.message}`);
    process.exit(1);
  }
}

// Run the script
main().catch(console.error);