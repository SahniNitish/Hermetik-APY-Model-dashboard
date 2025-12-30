/**
 * QUICK STABLECOIN DATA FETCHER (June-August 2024)
 * =================================================
 * Uses known stablecoin pool addresses for faster collection
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

// Known major stablecoin pools (from our metadata analysis)
const KNOWN_STABLECOIN_POOLS = [
  '0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640', // USDC/WETH but has some USDC/USDT
  '0x8ad599c3a0ff1de082011efddc58f1908eb6e6d8', // USDC/USDT  
  '0x5777d92f208679db4b9778590fa3cab3ac9e2168', // DAI/USDC
  '0x6c6bc977e13df9b0de53b251522280bb72383700', // DAI/USDT
  '0x3416cf6c708da44db2624d63ea0aaef7113527c6', // USDC/USDT
  '0xa63b490aa077f541c9d64bfc1cc0db2a752157b5', // FRAX/USDC
  '0x97e7d56a0408570ba1a7852de36350f7713906ec', // FRAX/USDT
  '0x4e0924d3a751be199c426d52fb1f2337fa96f736', // LUSD/USDC
  '0xc2e9f25be6257c210d7adf0d4cd6e3e881ba25f8', // DAI/FRAX
  '0x6f7c96c0ab5b742c8b4e2d4bba995fcc0a31a55c', // USDC/USDP
];

// Uniswap V3 Swap event signature
const SWAP_EVENT_TOPIC = '0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67';

// Date configuration - just sample a few key dates for speed
const TARGET_DATES = [
  { label: 'June 15', date: '2024-06-15' },
  { label: 'July 15', date: '2024-07-15' }, 
  { label: 'August 15', date: '2024-08-15' }
];

// Configuration
const BLOCKS_PER_DAY = 7200;
const DELAY_MS = 1000;

/**
 * Get block number for a specific date
 */
async function getBlockByDate(targetDate) {
  console.log(`🔍 Finding block for ${targetDate}...`);
  
  const targetTimestamp = Math.floor(new Date(targetDate + 'T00:00:00Z').getTime() / 1000);
  let left = 15000000;
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
 * Fetch stablecoin swap data for a specific day
 */
async function fetchStablecoinSwaps(targetDate, blockNumber) {
  console.log(`\n📅 Fetching swaps for ${targetDate}...`);
  
  const fromBlock = blockNumber;
  const toBlock = blockNumber + BLOCKS_PER_DAY;
  
  const stablecoinTransactions = [];
  
  try {
    // Get all Uniswap swaps for the day
    const logs = await provider.getLogs({
      fromBlock: fromBlock,
      toBlock: toBlock,
      topics: [SWAP_EVENT_TOPIC]
    });
    
    console.log(`  📊 Found ${logs.length} total swaps`);
    
    // Filter for known stablecoin pools
    const stablecoinLogs = logs.filter(log => 
      KNOWN_STABLECOIN_POOLS.includes(log.address.toLowerCase())
    );
    
    console.log(`  💰 ${stablecoinLogs.length} from known stablecoin pools`);
    
    // Process transactions
    for (const log of stablecoinLogs) {
      stablecoinTransactions.push({
        blockNumber: log.blockNumber,
        transactionHash: log.transactionHash,
        poolAddress: log.address.toLowerCase(),
        date: targetDate,
        logIndex: log.logIndex
      });
    }
    
    console.log(`✅ Collected ${stablecoinTransactions.length} stablecoin transactions`);
    
  } catch (error) {
    console.error(`❌ Error fetching data for ${targetDate}: ${error.message}`);
  }
  
  return stablecoinTransactions;
}

/**
 * Get pool token information
 */
async function getPoolInfo(poolAddress) {
  try {
    const poolContract = new ethers.Contract(poolAddress, [
      'function token0() external view returns (address)',
      'function token1() external view returns (address)',
      'function fee() external view returns (uint24)'
    ], provider);
    
    const [token0, token1, fee] = await Promise.all([
      poolContract.token0(),
      poolContract.token1(), 
      poolContract.fee()
    ]);
    
    // Get token symbols
    const token0Contract = new ethers.Contract(token0, [
      'function symbol() external view returns (string)'
    ], provider);
    const token1Contract = new ethers.Contract(token1, [
      'function symbol() external view returns (string)'
    ], provider);
    
    const [symbol0, symbol1] = await Promise.all([
      token0Contract.symbol().catch(() => 'UNKNOWN'),
      token1Contract.symbol().catch(() => 'UNKNOWN')
    ]);
    
    return {
      poolAddress: poolAddress.toLowerCase(),
      token0: token0.toLowerCase(),
      token1: token1.toLowerCase(),
      symbol0,
      symbol1,
      fee: fee.toString(),
      poolName: `${symbol0}/${symbol1}`
    };
    
  } catch (error) {
    console.error(`Error getting info for pool ${poolAddress}: ${error.message}`);
    return null;
  }
}

/**
 * Save data to CSV
 */
function saveTransactionsToCSV(transactions, filename) {
  if (transactions.length === 0) {
    console.log(`⚠️  No transactions to save for ${filename}`);
    return;
  }
  
  const outputPath = path.join(__dirname, 'static', filename);
  
  const header = 'blockNumber,transactionHash,poolAddress,date,logIndex\n';
  const csvContent = header + transactions.map(tx => 
    `${tx.blockNumber},${tx.transactionHash},${tx.poolAddress},${tx.date},${tx.logIndex}`
  ).join('\n');
  
  fs.writeFileSync(outputPath, csvContent);
  console.log(`💾 Saved ${transactions.length} transactions to ${filename}`);
}

/**
 * Save pool info to CSV
 */
function savePoolInfoToCSV(poolInfos, filename) {
  if (poolInfos.length === 0) {
    console.log(`⚠️  No pool info to save`);
    return;
  }
  
  const outputPath = path.join(__dirname, 'static', filename);
  
  const header = 'poolAddress,token0,token1,symbol0,symbol1,fee,poolName\n';
  const csvContent = header + poolInfos.map(info => 
    `${info.poolAddress},${info.token0},${info.token1},${info.symbol0},${info.symbol1},${info.fee},${info.poolName}`
  ).join('\n');
  
  fs.writeFileSync(outputPath, csvContent);
  console.log(`💾 Saved ${poolInfos.length} pool infos to ${filename}`);
}

/**
 * Sleep utility
 */
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Main execution
 */
async function main() {
  console.log('================================================================================');
  console.log('QUICK STABLECOIN DATA FETCHER (June-August 2024)');
  console.log('================================================================================');
  console.log(`🎯 Targeting ${KNOWN_STABLECOIN_POOLS.length} known stablecoin pools`);
  console.log(`📅 Sampling ${TARGET_DATES.length} key dates`);
  
  try {
    const allTransactions = [];
    const poolInfoMap = new Map();
    
    // Fetch pool information first
    console.log('\n📊 Getting pool information...');
    for (const poolAddress of KNOWN_STABLECOIN_POOLS) {
      const info = await getPoolInfo(poolAddress);
      if (info) {
        poolInfoMap.set(poolAddress, info);
        console.log(`  ✅ ${info.poolName} (${info.fee} fee)`);
      }
      await sleep(200); // Rate limit
    }
    
    // Fetch transaction data for each date
    for (const {label, date} of TARGET_DATES) {
      try {
        const blockNumber = await getBlockByDate(date);
        const transactions = await fetchStablecoinSwaps(date, blockNumber);
        allTransactions.push(...transactions);
        
        // Save individual day data
        saveTransactionsToCSV(transactions, `stablecoin_txs_${date}.csv`);
        
        await sleep(DELAY_MS);
        
      } catch (error) {
        console.error(`❌ Error processing ${date}: ${error.message}`);
        continue;
      }
    }
    
    // Save combined data
    saveTransactionsToCSV(allTransactions, 'stablecoin_transactions_june_august_sample.csv');
    
    // Save pool information
    const poolInfos = Array.from(poolInfoMap.values());
    savePoolInfoToCSV(poolInfos, 'stablecoin_pools_info.csv');
    
    console.log('\n================================================================================');
    console.log('✅ QUICK STABLECOIN DATA COLLECTION COMPLETE!');
    console.log('================================================================================');
    console.log(`📊 Total transactions: ${allTransactions.length.toLocaleString()}`);
    console.log(`🏊 Pools covered: ${poolInfos.length}`);
    console.log(`📅 Date range: June-August 2024 (sampled)`);
    
    // Summary by date
    const dateGroups = {};
    allTransactions.forEach(tx => {
      dateGroups[tx.date] = (dateGroups[tx.date] || 0) + 1;
    });
    
    console.log('\n📊 Transactions by date:');
    for (const [date, count] of Object.entries(dateGroups)) {
      console.log(`   ${date}: ${count.toLocaleString()} transactions`);
    }
    
    // Summary by pool
    const poolGroups = {};
    allTransactions.forEach(tx => {
      const poolInfo = poolInfoMap.get(tx.poolAddress);
      const poolName = poolInfo ? poolInfo.poolName : tx.poolAddress;
      poolGroups[poolName] = (poolGroups[poolName] || 0) + 1;
    });
    
    console.log('\n🏊 Top active pools:');
    const sortedPools = Object.entries(poolGroups)
      .sort(([,a], [,b]) => b - a)
      .slice(0, 5);
      
    for (const [poolName, count] of sortedPools) {
      console.log(`   ${poolName}: ${count.toLocaleString()} transactions`);
    }
    
    console.log('\n📁 Output files:');
    console.log('   - stablecoin_transactions_june_august_sample.csv (all transactions)');
    console.log('   - stablecoin_pools_info.csv (pool metadata)');
    console.log('   - Individual daily files: stablecoin_txs_YYYY-MM-DD.csv');
    
  } catch (error) {
    console.error(`❌ Fatal error: ${error.message}`);
    process.exit(1);
  }
}

// Run the script
main().catch(console.error);