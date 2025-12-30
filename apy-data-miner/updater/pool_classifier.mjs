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

// Additional stablecoins
const TUSD = '0x0000000000085d4780b73119b644ae5ecd22b376';
const GUSD = '0x056fd409e1d7a124bd7017459dfea2f387b6d5cd';
const PYUSD = '0x6c3ea9036406852006290770bedfcaba0e23a0e8';
const USDE = '0x4c9edd5852cd905f086c759e8383e09bff1e68b3';
const GHO = '0x40d16fc0246ad3160ccc09b8d0d3a2cd28ae6c2f';
const SUSDE = '0x9d39a5de30e57443bff2a8307a4256c8797a3497';
const USDS = '0xdc035d45d973e3ec169d2276ddab16f1e407384f';
const SUSDS = '0xa3931d71877c0e7a3148cb7eb4463524fec27fbd';
const FRXUSD = '0xcacd6fd266af91b8aed52accc382b4e165586e29';
const FRAXBP = '0x3175df0976dfa876431c2e9ee6bc45b65d3473cc';
const RLUSD = '0x8292bb45bf1ee4d140127049757c2e0ff06317ed';
const SYRUPUSDC = '0x80ac24aa929eaf5013f6436cda2a7ba190f5cc0b';

// Additional established stablecoins
const MUSD = '0xe2f2a5c287993345a840db3b0845fbc70f5935a5';
const UST = '0xa693b19d2931d498c5b318df961919bb4aee87a5';
const USDP = '0x8e870d67f660d95d5be530380d0ec0bd388289e1';
const EUROC = '0x1abaea1f7c830bd89acc67ec4af516284b1bc33c';
const EURT = '0xc581b735a1688071a1746c968e0798d642ede491';
const USDD = '0x0c10bf8fcb7bf5412187a595ab97a3609160b5c6';
const USTC = '0xa47c8bf37f92abed4a126bda807a7b7498661acd';
const WCUSD = '0xad3e3fc59dff318beceaab7d00eb4f68b1ecf195';
const OUSD = '0x2a8e1e676ec238d8a992307b495b45b3feaa5e86';

const STABLECOINS = new Set([
  USDC, USDT, DAI, FRAX, LUSD, BUSD, TUSD, GUSD, PYUSD, USDE, GHO,
  SUSDE, USDS, SUSDS, FRXUSD, FRAXBP, RLUSD, SYRUPUSDC,
  MUSD, UST, USDP, EUROC, EURT, USDD, USTC, WCUSD, OUSD
]);

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
