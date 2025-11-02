/**
 * Pool State Fetcher - Fetches pool state data from Ethereum using Alchemy API
 * Focuses on ETH pools and calculates TVL, reserves, and fee metrics
 */

import { ethers } from 'ethers';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Load environment variables
import dotenv from 'dotenv';
dotenv.config({ path: path.join(__dirname, '.env') });

const ALCHEMY_KEY = process.env.ALCHEMY_API_KEY;
if (!ALCHEMY_KEY) {
  throw new Error('ALCHEMY_API_KEY not set in .env file');
}

const provider = new ethers.JsonRpcProvider(
  `https://eth-mainnet.g.alchemy.com/v2/${ALCHEMY_KEY}`
);

// WETH address on Ethereum mainnet
const WETH_ADDRESS = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2";

// Minimal ABIs for pool state queries
const UNISWAP_V3_POOL_ABI = [
  "function token0() view returns (address)",
  "function token1() view returns (address)",
  "function liquidity() view returns (uint128)",
  "function slot0() view returns (uint160 sqrtPriceX96, int24 tick, uint16 observationIndex, uint16 observationCardinality, uint16 observationCardinalityNext, uint8 feeProtocol, bool unlocked)",
  "function fee() view returns (uint24)"
];

const UNISWAP_V2_POOL_ABI = [
  "function token0() view returns (address)",
  "function token1() view returns (address)",
  "function getReserves() view returns (uint112 reserve0, uint112 reserve1, uint32 blockTimestampLast)"
];

const ERC20_ABI = [
  "function balanceOf(address) view returns (uint256)",
  "function decimals() view returns (uint8)",
  "function symbol() view returns (string)",
  "function name() view returns (string)"
];

// Swap event signature for Uniswap V3
const SWAP_EVENT_SIGNATURE = "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67";

/**
 * Check if an address is WETH
 */
function isWETH(address) {
  return address.toLowerCase() === WETH_ADDRESS.toLowerCase();
}

/**
 * Get token metadata (symbol, decimals, name)
 */
async function getTokenMetadata(tokenAddress) {
  try {
    const token = new ethers.Contract(tokenAddress, ERC20_ABI, provider);
    const [symbol, decimals, name] = await Promise.all([
      token.symbol(),
      token.decimals(),
      token.name()
    ]);
    return { symbol, decimals, name, address: tokenAddress };
  } catch (error) {
    console.error(`Error fetching metadata for ${tokenAddress}: ${error.message}`);
    return {
      symbol: 'UNKNOWN',
      decimals: 18,
      name: 'Unknown Token',
      address: tokenAddress
    };
  }
}

/**
 * Fetch Uniswap V3 pool state
 */
async function fetchUniV3PoolState(poolAddress) {
  try {
    const pool = new ethers.Contract(poolAddress, UNISWAP_V3_POOL_ABI, provider);

    // Fetch all pool data in parallel
    const [token0Addr, token1Addr, liquidity, slot0, feeTier] = await Promise.all([
      pool.token0(),
      pool.token1(),
      pool.liquidity(),
      pool.slot0(),
      pool.fee()
    ]);

    // Check if this is an ETH pool
    const hasETH = isWETH(token0Addr) || isWETH(token1Addr);
    if (!hasETH) {
      return null; // Skip non-ETH pools
    }

    // Get token metadata
    const [token0Meta, token1Meta] = await Promise.all([
      getTokenMetadata(token0Addr),
      getTokenMetadata(token1Addr)
    ]);

    // Get actual reserves (token balances in pool)
    const token0Contract = new ethers.Contract(token0Addr, ERC20_ABI, provider);
    const token1Contract = new ethers.Contract(token1Addr, ERC20_ABI, provider);

    const [reserve0, reserve1] = await Promise.all([
      token0Contract.balanceOf(poolAddress),
      token1Contract.balanceOf(poolAddress)
    ]);

    // Calculate price from sqrtPriceX96
    const sqrtPriceX96 = slot0.sqrtPriceX96;
    const price = (Number(sqrtPriceX96) / (2 ** 96)) ** 2;

    // Adjust price for decimals
    const priceAdjusted = price * (10 ** token0Meta.decimals) / (10 ** token1Meta.decimals);

    return {
      poolAddress,
      protocol: 'Uniswap V3',
      token0: token0Meta,
      token1: token1Meta,
      reserve0: reserve0.toString(),
      reserve1: reserve1.toString(),
      reserve0Formatted: ethers.formatUnits(reserve0, token0Meta.decimals),
      reserve1Formatted: ethers.formatUnits(reserve1, token1Meta.decimals),
      liquidity: liquidity.toString(),
      currentPrice: priceAdjusted,
      sqrtPriceX96: sqrtPriceX96.toString(),
      tick: slot0.tick,
      feeTier: feeTier, // In hundredths of a bip (3000 = 0.3%)
      feePercentage: Number(feeTier) / 10000, // Convert to percentage
      hasETH: true,
      ethIsToken0: isWETH(token0Addr),
      pairedToken: isWETH(token0Addr) ? token1Meta : token0Meta,
      ethReserve: isWETH(token0Addr) ? reserve0 : reserve1,
      ethReserveFormatted: isWETH(token0Addr)
        ? ethers.formatEther(reserve0)
        : ethers.formatEther(reserve1)
    };
  } catch (error) {
    console.error(`Error fetching V3 pool state for ${poolAddress}: ${error.message}`);
    return null;
  }
}

/**
 * Fetch Uniswap V2 pool state
 */
async function fetchUniV2PoolState(poolAddress) {
  try {
    const pool = new ethers.Contract(poolAddress, UNISWAP_V2_POOL_ABI, provider);

    const [token0Addr, token1Addr, reserves] = await Promise.all([
      pool.token0(),
      pool.token1(),
      pool.getReserves()
    ]);

    // Check if this is an ETH pool
    const hasETH = isWETH(token0Addr) || isWETH(token1Addr);
    if (!hasETH) {
      return null; // Skip non-ETH pools
    }

    // Get token metadata
    const [token0Meta, token1Meta] = await Promise.all([
      getTokenMetadata(token0Addr),
      getTokenMetadata(token1Addr)
    ]);

    const reserve0 = reserves.reserve0;
    const reserve1 = reserves.reserve1;

    return {
      poolAddress,
      protocol: 'Uniswap V2',
      token0: token0Meta,
      token1: token1Meta,
      reserve0: reserve0.toString(),
      reserve1: reserve1.toString(),
      reserve0Formatted: ethers.formatUnits(reserve0, token0Meta.decimals),
      reserve1Formatted: ethers.formatUnits(reserve1, token1Meta.decimals),
      feeTier: 3000, // V2 has fixed 0.3% fee
      feePercentage: 0.003,
      hasETH: true,
      ethIsToken0: isWETH(token0Addr),
      pairedToken: isWETH(token0Addr) ? token1Meta : token0Meta,
      ethReserve: isWETH(token0Addr) ? reserve0 : reserve1,
      ethReserveFormatted: isWETH(token0Addr)
        ? ethers.formatEther(reserve0)
        : ethers.formatEther(reserve1)
    };
  } catch (error) {
    console.error(`Error fetching V2 pool state for ${poolAddress}: ${error.message}`);
    return null;
  }
}

/**
 * Get swap events for a pool to calculate fee revenue
 */
async function getSwapEvents(poolAddress, fromBlock, toBlock) {
  try {
    const logs = await provider.getLogs({
      address: poolAddress,
      topics: [SWAP_EVENT_SIGNATURE],
      fromBlock,
      toBlock
    });

    return logs.map(log => ({
      blockNumber: log.blockNumber,
      transactionHash: log.transactionHash,
      logIndex: log.logIndex
    }));
  } catch (error) {
    console.error(`Error fetching swap events for ${poolAddress}: ${error.message}`);
    return [];
  }
}

/**
 * Calculate TVL in USD (requires ETH price)
 */
function calculateTVL(poolState, ethPriceUSD) {
  try {
    const ethReserve = Number(poolState.ethReserveFormatted);
    // TVL = 2 * ETH reserve value (assuming balanced pool)
    const tvl = 2 * ethReserve * ethPriceUSD;
    return tvl;
  } catch (error) {
    console.error(`Error calculating TVL: ${error.message}`);
    return 0;
  }
}

/**
 * Fetch ETH price from Chainlink or a major ETH/USDC pool
 */
async function getETHPriceUSD() {
  try {
    // Using Uniswap V3 ETH/USDC 0.05% pool as price oracle
    const ETH_USDC_POOL = "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640";
    const poolState = await fetchUniV3PoolState(ETH_USDC_POOL);

    if (poolState) {
      // If ETH is token0, price is in terms of USDC per ETH
      // If ETH is token1, we need to invert
      const ethPrice = poolState.ethIsToken0
        ? poolState.currentPrice
        : 1 / poolState.currentPrice;

      console.log(`📊 ETH Price: $${ethPrice.toFixed(2)}`);
      return ethPrice;
    }

    // Fallback to approximate price
    console.warn('Could not fetch ETH price, using fallback value');
    return 2500; // Fallback value
  } catch (error) {
    console.error(`Error fetching ETH price: ${error.message}`);
    return 2500; // Fallback value
  }
}

/**
 * Batch fetch pool states for multiple pools
 */
async function batchFetchPoolStates(poolAddresses, protocol = 'v3') {
  const results = [];
  const fetchFunction = protocol === 'v3' ? fetchUniV3PoolState : fetchUniV2PoolState;

  for (const poolAddr of poolAddresses) {
    const state = await fetchFunction(poolAddr);
    if (state) {
      results.push(state);
    }
    // Rate limiting
    await new Promise(resolve => setTimeout(resolve, 100));
  }

  return results;
}

/**
 * Save pool states to CSV
 */
function savePoolStatesToCSV(poolStates, outputPath) {
  const headers = [
    'Pool Address',
    'Protocol',
    'Token0 Symbol',
    'Token1 Symbol',
    'Paired Token',
    'ETH Reserve',
    'Paired Token Reserve',
    'Fee Tier',
    'Fee %',
    'Current Price',
    'TVL (ETH)',
    'Timestamp'
  ];

  const rows = poolStates.map(state => [
    state.poolAddress,
    state.protocol,
    state.token0.symbol,
    state.token1.symbol,
    state.pairedToken.symbol,
    state.ethReserveFormatted,
    state.ethIsToken0 ? state.reserve1Formatted : state.reserve0Formatted,
    state.feeTier,
    state.feePercentage,
    state.currentPrice || 'N/A',
    (2 * Number(state.ethReserveFormatted)).toFixed(4),
    new Date().toISOString()
  ]);

  const csv = [headers.join(','), ...rows.map(row => row.join(','))].join('\n');
  fs.writeFileSync(outputPath, csv);
  console.log(`✅ Saved ${poolStates.length} pool states to ${outputPath}`);
}

export {
  fetchUniV3PoolState,
  fetchUniV2PoolState,
  getSwapEvents,
  calculateTVL,
  getETHPriceUSD,
  batchFetchPoolStates,
  savePoolStatesToCSV,
  getTokenMetadata,
  WETH_ADDRESS,
  isWETH
};
