/**
 * STABLECOIN HISTORICAL DATA FETCHER (Jan 1 - March 1, 2025)
 * ==========================================================
 * Fetches transaction data for stablecoin pools only from January 1 to March 1, 2025
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
  '0x8e870d67f660d95d5be530380d0ec0bd388289e1', // USDP
  '0x1abaea1f7c830bd89acc67ec4af516284b1bc33c', // EUROC
  '0xc581b735a1688071a1746c968e0798d642ede491', // EURT
  '0x0c10bf8fcb7bf5412187a595ab97a3609160b5c6', // USDD
  '0xa47c8bf37f92abed4a126bda807a7b7498661acd', // USTC
  '0xad3e3fc59dff318beceaab7d00eb4f68b1ecf195', // WCUSD
  '0x2a8e1e676ec238d8a992307b495b45b3feaa5e86'  // OUSD
]);

// Load stablecoin pools from our metadata
let STABLECOIN_POOLS = new Set();

// Uniswap V3 Swap event signature
const SWAP_EVENT_TOPIC = '0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67';

// Generate month-wise data collection - starting with recent months
function generateMonthRange(year, startMonth, endMonth) {
  const dates = {};
  
  for (let month = startMonth; month <= endMonth; month++) {
    // Get first and mid-month dates for sampling
    const firstDate = new Date(year, month - 1, 1);
    const midDate = new Date(year, month - 1, 15);
    
    const firstStr = firstDate.toISOString().split('T')[0];
    const midStr = midDate.toISOString().split('T')[0];
    
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                       'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    
    dates[`${monthNames[month-1]} 1`] = firstStr;
    dates[`${monthNames[month-1]} 15`] = midStr;
  }
  
  return dates;
}

// January to March 2025 data collection
const TARGET_DATES = generateMonthRange(2025, 1, 3);

// Configuration
const BLOCKS_PER_DAY = 7200;
const BATCH_SIZE = 2000;
const DELAY_MS = 1500; // Increased delay for stability

/**
 * Get block number for a specific date
 */
async function getBlockByDate(targetDate) {
  console.log(`🔍 Finding block number for ${targetDate}...`);
  
  const targetTimestamp = Math.floor(new Date(targetDate + 'T00:00:00Z').getTime() / 1000);
  let left = 21500000; // Approximate block around early 2025
  let right = await provider.getBlockNumber();
  
  while (left < right) {
    const mid = Math.floor((left + right) / 2);
    const block = await provider.getBlock(mid);
    
    if (block.timestamp < targetTimestamp) {
      left = mid + 1;
    } else {
      right = mid;
    }
    
    // Progress indicator
    if ((right - left) % 1000 === 0) {
      process.stdout.write('.');
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
    const lines = csvData.split('\n').slice(1); // Skip header
    
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
  // First check our loaded metadata
  if (STABLECOIN_POOLS.has(poolAddress.toLowerCase())) {
    return true;
  }
  
  try {
    // Fallback: check token addresses directly
    const poolContract = new ethers.Contract(poolAddress, [
      'function token0() external view returns (address)',
      'function token1() external view returns (address)'
    ], provider);
    
    const [token0, token1] = await Promise.all([
      poolContract.token0(),
      poolContract.token1()
    ]);
    
    const isToken0Stable = STABLECOINS.has(token0.toLowerCase());
    const isToken1Stable = STABLECOINS.has(token1.toLowerCase());
    
    return isToken0Stable && isToken1Stable;
  } catch (error) {
    return false;
  }
}

/**
 * Fetch transactions for a specific day
 */
async function fetchStablecoinDataForDay(targetDate, blockNumber) {
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
      
      // Filter for stablecoin pools only
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
      
      // Rate limiting
      if (processedBatches < totalBatches) {
        await sleep(DELAY_MS);
      }
      
    } catch (error) {
      console.error(`    ❌ Error in batch ${processedBatches}: ${error.message}`);
      continue;
    }
  }
  
  console.log(`✅ ${targetDate}: Collected ${allTransactions.length} stablecoin transactions`);
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
  console.log('STABLECOIN HISTORICAL DATA FETCHER (January 1 - March 1, 2025)');
  console.log('================================================================================');
  
  try {
    // Load stablecoin pool addresses
    const poolsLoaded = loadStablecoinPools();
    if (!poolsLoaded) {
      console.log('⚠️  Warning: No pool metadata found. Will check pools dynamically (slower).');
    }
    
    const allTransactions = [];
    
    // Fetch data for each target date
    for (const [label, dateString] of Object.entries(TARGET_DATES)) {
      try {
        const blockNumber = await getBlockByDate(dateString);
        const dayTransactions = await fetchStablecoinDataForDay(dateString, blockNumber);
        allTransactions.push(...dayTransactions);
        
        // Save individual day data
        saveToCSV(dayTransactions, `stablecoin_txs_${dateString}.csv`);
        
      } catch (error) {
        console.error(`❌ Error fetching data for ${dateString}: ${error.message}`);
        continue;
      }
    }
    
    // Save combined data
    saveToCSV(allTransactions, 'stablecoin_transactions_jan_mar_2025.csv');
    
    console.log('\n================================================================================');
    console.log('✅ STABLECOIN HISTORICAL DATA COLLECTION COMPLETE!');
    console.log('================================================================================');
    console.log(`📊 Total stablecoin transactions collected: ${allTransactions.length.toLocaleString()}`);
    console.log(`📅 Date range: January 1 - March 1, 2025`);
    console.log(`🎯 Pools covered: ${STABLECOIN_POOLS.size} stablecoin pools`);
    
    // Summary by date
    const dateGroups = {};
    allTransactions.forEach(tx => {
      dateGroups[tx.date] = (dateGroups[tx.date] || 0) + 1;
    });
    
    console.log('\n📊 Transactions by date:');
    for (const [date, count] of Object.entries(dateGroups)) {
      console.log(`   ${date}: ${count.toLocaleString()} transactions`);
    }
    
  } catch (error) {
    console.error(`❌ Fatal error: ${error.message}`);
    process.exit(1);
  }
}

// Run the script
main().catch(console.error);