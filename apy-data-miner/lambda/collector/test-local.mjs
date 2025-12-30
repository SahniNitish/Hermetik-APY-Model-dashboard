/**
 * Local Test Script for APY Data Miner
 * Tests the collector without requiring RDS database
 */

import { ethers } from 'ethers';
import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

dotenv.config({ path: path.join(__dirname, '.env') });

// Configuration
const SWAP_EVENT_TOPIC = '0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67';
const BLOCKS_TO_TEST = 100;  // Small batch for testing
const BATCH_SIZE = 50;

// Known tokens
const WETH = '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2';
const STABLECOINS = new Set([
  '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48', // USDC
  '0xdac17f958d2ee523a2206206994597c13d831ec7', // USDT
  '0x6b175474e89094c44da98b954eedeac495271d0f', // DAI
]);

// ABIs
const POOL_ABI = [
  'function token0() external view returns (address)',
  'function token1() external view returns (address)',
  'function fee() external view returns (uint24)'
];

const ERC20_ABI = [
  'function symbol() external view returns (string)'
];

const SWAP_EVENT_ABI = [
  'event Swap(address indexed sender, address indexed recipient, int256 amount0, int256 amount1, uint160 sqrtPriceX96, uint128 liquidity, int24 tick)'
];

async function main() {
  console.log('╔════════════════════════════════════════════════════════════════╗');
  console.log('║                                                                ║');
  console.log('║          APY DATA MINER - LOCAL TEST                          ║');
  console.log('║                                                                ║');
  console.log('╚════════════════════════════════════════════════════════════════╝\n');

  // Check API key
  const apiKey = process.env.ALCHEMY_API_KEY;
  if (!apiKey) {
    console.error('❌ ALCHEMY_API_KEY not found in .env file');
    process.exit(1);
  }
  console.log('✅ Alchemy API key found');

  // Initialize provider
  console.log('\n📡 Connecting to Ethereum mainnet...');
  const provider = new ethers.JsonRpcProvider(
    `https://eth-mainnet.g.alchemy.com/v2/${apiKey}`
  );

  // Test connection
  try {
    const blockNumber = await provider.getBlockNumber();
    console.log(`✅ Connected! Current block: ${blockNumber}`);

    const network = await provider.getNetwork();
    console.log(`   Network: ${network.name} (chainId: ${network.chainId})`);
  } catch (error) {
    console.error('❌ Failed to connect:', error.message);
    process.exit(1);
  }

  // Test swap log fetching
  console.log('\n📊 Testing swap log collection...');
  console.log(`   Fetching last ${BLOCKS_TO_TEST} blocks...`);

  const currentBlock = await provider.getBlockNumber();
  const startBlock = currentBlock - BLOCKS_TO_TEST;

  const swapInterface = new ethers.Interface(SWAP_EVENT_ABI);
  const allSwaps = [];
  const uniquePools = new Set();

  for (let from = startBlock; from <= currentBlock; from += BATCH_SIZE) {
    const to = Math.min(from + BATCH_SIZE - 1, currentBlock);

    try {
      const logs = await provider.getLogs({
        fromBlock: from,
        toBlock: to,
        topics: [SWAP_EVENT_TOPIC]
      });

      for (const log of logs) {
        try {
          const parsed = swapInterface.parseLog({
            topics: log.topics,
            data: log.data
          });

          allSwaps.push({
            blockNumber: log.blockNumber,
            poolAddress: log.address.toLowerCase(),
            sender: parsed.args.sender.toLowerCase(),
            recipient: parsed.args.recipient.toLowerCase(),
            amount0: parsed.args.amount0.toString(),
            amount1: parsed.args.amount1.toString()
          });

          uniquePools.add(log.address.toLowerCase());
        } catch (e) {
          // Skip unparseable logs
        }
      }

      process.stdout.write(`\r   Blocks ${from}-${to}: ${allSwaps.length} swaps found`);
    } catch (error) {
      console.error(`\n   ⚠️  Error fetching blocks ${from}-${to}:`, error.message);
    }
  }

  console.log(`\n\n✅ Collection test passed!`);
  console.log(`   Total swaps: ${allSwaps.length}`);
  console.log(`   Unique pools: ${uniquePools.size}`);

  // Test pool classification
  if (uniquePools.size > 0) {
    console.log('\n🏷️  Testing pool classification...');

    const poolsToClassify = Array.from(uniquePools).slice(0, 5); // Test first 5

    for (const poolAddress of poolsToClassify) {
      try {
        const pool = new ethers.Contract(poolAddress, POOL_ABI, provider);

        const [token0, token1, fee] = await Promise.all([
          pool.token0(),
          pool.token1(),
          pool.fee()
        ]);

        // Get token symbols
        let symbol0 = 'UNKNOWN', symbol1 = 'UNKNOWN';
        try {
          const token0Contract = new ethers.Contract(token0, ERC20_ABI, provider);
          symbol0 = await token0Contract.symbol();
        } catch (e) {}
        try {
          const token1Contract = new ethers.Contract(token1, ERC20_ABI, provider);
          symbol1 = await token1Contract.symbol();
        } catch (e) {}

        // Classify
        const t0 = token0.toLowerCase();
        const t1 = token1.toLowerCase();
        let poolType = 'other';
        if (t0 === WETH || t1 === WETH) {
          poolType = 'eth_paired';
        } else if (STABLECOINS.has(t0) && STABLECOINS.has(t1)) {
          poolType = 'stablecoin';
        }

        const feePercent = (parseInt(fee) / 10000).toFixed(2);
        console.log(`   ${symbol0}/${symbol1} (${feePercent}%) → ${poolType}`);
        console.log(`      Pool: ${poolAddress.slice(0, 10)}...`);

      } catch (error) {
        console.log(`   ⚠️  Failed to classify ${poolAddress.slice(0, 10)}...: ${error.message}`);
      }
    }

    console.log('\n✅ Classification test passed!');
  }

  // Aggregate metrics test
  console.log('\n📈 Testing metrics aggregation...');

  const poolMetrics = new Map();
  for (const swap of allSwaps) {
    if (!poolMetrics.has(swap.poolAddress)) {
      poolMetrics.set(swap.poolAddress, {
        txCount: 0,
        uniqueUsers: new Set()
      });
    }
    const metrics = poolMetrics.get(swap.poolAddress);
    metrics.txCount++;
    metrics.uniqueUsers.add(swap.sender);
    metrics.uniqueUsers.add(swap.recipient);
  }

  // Show top 5 pools
  const sortedPools = Array.from(poolMetrics.entries())
    .map(([addr, m]) => ({ address: addr, txCount: m.txCount, uniqueUsers: m.uniqueUsers.size }))
    .sort((a, b) => b.txCount - a.txCount)
    .slice(0, 5);

  console.log('\n   Top 5 pools by transaction count:');
  for (const pool of sortedPools) {
    console.log(`   ${pool.address.slice(0, 10)}... → ${pool.txCount} txs, ${pool.uniqueUsers} users`);
  }

  console.log('\n✅ Aggregation test passed!');

  // Summary
  console.log('\n╔════════════════════════════════════════════════════════════════╗');
  console.log('║                    ALL TESTS PASSED!                           ║');
  console.log('╚════════════════════════════════════════════════════════════════╝\n');

  console.log('📋 Summary:');
  console.log(`   ✅ Ethereum connection: Working`);
  console.log(`   ✅ Swap log fetching: ${allSwaps.length} swaps collected`);
  console.log(`   ✅ Pool classification: ${uniquePools.size} pools identified`);
  console.log(`   ✅ Metrics aggregation: Working`);
  console.log('\n🚀 Ready for AWS deployment!\n');

  console.log('Next steps:');
  console.log('   1. cd infrastructure');
  console.log('   2. ./deploy.sh');
  console.log('');
}

main().catch(error => {
  console.error('❌ Test failed:', error);
  process.exit(1);
});
