/**
 * Pool Classifier - Fetch metadata and classify pools
 * Identifies ETH pools, stablecoin pools, and other token pools
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
  throw new Error('ALCHEMY_API_KEY not found');
}

const provider = new ethers.JsonRpcProvider(
  `https://eth-mainnet.g.alchemy.com/v2/${ALCHEMY_API_KEY}`
);

// Known token addresses (lowercase)
const WETH = '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2';
const USDC = '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48';
const USDT = '0xdac17f958d2ee523a2206206994597c13d831ec7';
const DAI = '0x6b175474e89094c44da98b954eedeac495271d0f';
const FRAX = '0x853d955acef822db058eb8505911ed77f175b99e';
const LUSD = '0x5f98805a4e8be255a32880fdec7f6728c6568ba0';
const BUSD = '0x4fabb145d64652a948d72533023f6e7a623c7c53';

const STABLECOINS = new Set([USDC, USDT, DAI, FRAX, LUSD, BUSD]);

// Contract ABIs
const POOL_ABI = [
  'function token0() external view returns (address)',
  'function token1() external view returns (address)',
  'function fee() external view returns (uint24)'
];

const ERC20_ABI = [
  'function symbol() external view returns (string)',
  'function decimals() external view returns (uint8)',
  'function name() external view returns (string)'
];

const OUTPUT_DIR = path.join(__dirname, 'static');
const BATCH_SIZE = 50; // Process 50 pools at a time
const DELAY_MS = 500;

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Fetch pool metadata
 */
async function fetchPoolMetadata(poolAddress) {
  try {
    const pool = new ethers.Contract(poolAddress, POOL_ABI, provider);

    const [token0, token1, fee] = await Promise.all([
      pool.token0(),
      pool.token1(),
      pool.fee()
    ]);

    return {
      token0: token0.toLowerCase(),
      token1: token1.toLowerCase(),
      fee: fee.toString()
    };
  } catch (error) {
    console.error(`  ✗ Failed to fetch pool ${poolAddress}:`, error.message);
    return null;
  }
}

/**
 * Fetch token metadata
 */
async function fetchTokenMetadata(tokenAddress) {
  try {
    const token = new ethers.Contract(tokenAddress, ERC20_ABI, provider);

    const [symbol, decimals] = await Promise.all([
      token.symbol(),
      token.decimals()
    ]);

    return { symbol, decimals: decimals.toString() };
  } catch (error) {
    // Some tokens don't follow standard ERC20
    return { symbol: 'UNKNOWN', decimals: '18' };
  }
}

/**
 * Classify pool type
 */
function classifyPool(token0, token1) {
  const isToken0ETH = token0 === WETH;
  const isToken1ETH = token1 === WETH;
  const isToken0Stable = STABLECOINS.has(token0);
  const isToken1Stable = STABLECOINS.has(token1);

  if (isToken0ETH || isToken1ETH) {
    return 'eth_paired';
  } else if (isToken0Stable && isToken1Stable) {
    return 'stablecoin';
  } else {
    return 'other';
  }
}

/**
 * Process pools in batches
 */
async function classifyAllPools(poolAddresses) {
  console.log('╔════════════════════════════════════════════════════════════════╗');
  console.log('║                                                                ║');
  console.log('║              POOL CLASSIFIER & METADATA FETCHER               ║');
  console.log('║                                                                ║');
  console.log('╚════════════════════════════════════════════════════════════════╝\n');

  console.log(`📊 Total pools to classify: ${poolAddresses.length}`);
  console.log(`📦 Batch size: ${BATCH_SIZE}`);
  console.log(`⏱️  Estimated time: ~${Math.ceil(poolAddresses.length / BATCH_SIZE * DELAY_MS / 1000 / 60)} minutes\n`);

  const outputFile = path.join(OUTPUT_DIR, 'pool_metadata.csv');

  // Write header
  const header = 'poolAddress,token0,token1,token0Symbol,token1Symbol,fee,poolType\n';
  fs.writeFileSync(outputFile, header);

  let processed = 0;
  let successful = 0;
  let failed = 0;
  const poolTypeCount = { eth_paired: 0, stablecoin: 0, other: 0 };

  console.log('🔄 Starting classification...\n');

  for (let i = 0; i < poolAddresses.length; i += BATCH_SIZE) {
    const batch = poolAddresses.slice(i, i + BATCH_SIZE);
    const batchNum = Math.floor(i / BATCH_SIZE) + 1;
    const totalBatches = Math.ceil(poolAddresses.length / BATCH_SIZE);

    // Process batch
    const results = await Promise.all(
      batch.map(async (poolAddress) => {
        try {
          // Get pool metadata
          const poolMeta = await fetchPoolMetadata(poolAddress);
          if (!poolMeta) return null;

          // Get token metadata
          const [token0Meta, token1Meta] = await Promise.all([
            fetchTokenMetadata(poolMeta.token0),
            fetchTokenMetadata(poolMeta.token1)
          ]);

          // Classify pool
          const poolType = classifyPool(poolMeta.token0, poolMeta.token1);

          return {
            poolAddress,
            token0: poolMeta.token0,
            token1: poolMeta.token1,
            token0Symbol: token0Meta.symbol,
            token1Symbol: token1Meta.symbol,
            fee: poolMeta.fee,
            poolType
          };
        } catch (error) {
          return null;
        }
      })
    );

    // Write successful results
    for (const result of results) {
      if (result) {
        const row = [
          result.poolAddress,
          result.token0,
          result.token1,
          result.token0Symbol,
          result.token1Symbol,
          result.fee,
          result.poolType
        ].join(',') + '\n';

        fs.appendFileSync(outputFile, row);
        successful++;
        poolTypeCount[result.poolType]++;
      } else {
        failed++;
      }
    }

    processed += batch.length;

    // Progress update every 10 batches
    if (batchNum % 10 === 0 || batchNum === totalBatches) {
      const progress = (processed / poolAddresses.length * 100).toFixed(1);
      console.log(`  ✓ Batch ${batchNum}/${totalBatches} (${progress}%)`);
      console.log(`    Success: ${successful} | Failed: ${failed}`);
      console.log(`    ETH pools: ${poolTypeCount.eth_paired} | Stablecoins: ${poolTypeCount.stablecoin} | Others: ${poolTypeCount.other}\n`);
    }

    // Rate limit protection
    if (i + BATCH_SIZE < poolAddresses.length) {
      await sleep(DELAY_MS);
    }
  }

  console.log('╔════════════════════════════════════════════════════════════════╗');
  console.log('║                  CLASSIFICATION COMPLETE!                     ║');
  console.log('╚════════════════════════════════════════════════════════════════╝\n');

  console.log(`✅ Results:`);
  console.log(`   Total processed: ${processed}`);
  console.log(`   Successful: ${successful}`);
  console.log(`   Failed: ${failed}\n`);

  console.log(`📊 Pool Type Breakdown:`);
  console.log(`   ETH-paired pools: ${poolTypeCount.eth_paired} (${(poolTypeCount.eth_paired/successful*100).toFixed(1)}%)`);
  console.log(`   Stablecoin pools: ${poolTypeCount.stablecoin} (${(poolTypeCount.stablecoin/successful*100).toFixed(1)}%)`);
  console.log(`   Other token pools: ${poolTypeCount.other} (${(poolTypeCount.other/successful*100).toFixed(1)}%)\n`);

  console.log(`💾 Saved to: ${outputFile}\n`);

  return { successful, failed, poolTypeCount };
}

/**
 * Main execution
 */
async function main() {
  try {
    // Read unique pools
    const poolsFile = path.join(OUTPUT_DIR, 'unique_pools.txt');
    const poolAddresses = fs.readFileSync(poolsFile, 'utf8')
      .split('\n')
      .filter(addr => addr.trim().length > 0)
      .map(addr => addr.trim().toLowerCase());

    await classifyAllPools(poolAddresses);

    console.log('🎉 Phase 2 Complete! Ready for Phase 3 (Time-Series Features)\n');

  } catch (error) {
    console.error('❌ Error:', error);
    process.exit(1);
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main();
}

export { classifyAllPools, classifyPool };
