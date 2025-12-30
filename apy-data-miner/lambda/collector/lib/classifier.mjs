/**
 * Pool Classifier Module
 * Identifies ETH pools, stablecoin pools, and other token pools
 */

import { ethers } from 'ethers';
import { getProvider } from './ethereum.mjs';

// Known token addresses (lowercase)
const WETH = '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2';

// Comprehensive stablecoin list
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
  '0x9d39a5de30e57443bff2a8307a4256c8797a3497', // sUSDE
  '0xdc035d45d973e3ec169d2276ddab16f1e407384f', // USDS
  '0xa3931d71877c0e7a3148cb7eb4463524fec27fbd', // sUSDS
  '0xcacd6fd266af91b8aed52accc382b4e165586e29', // FRXUSD
  '0x3175df0976dfa876431c2e9ee6bc45b65d3473cc', // FRAXBP
  '0x8292bb45bf1ee4d140127049757c2e0ff06317ed', // RLUSD
  '0x80ac24aa929eaf5013f6436cda2a7ba190f5cc0b', // syrupUSDC
  '0xe2f2a5c287993345a840db3b0845fbc70f5935a5', // mUSD
  '0xa693b19d2931d498c5b318df961919bb4aee87a5', // UST
  '0x8e870d67f660d95d5be530380d0ec0bd388289e1', // USDP
  '0x1abaea1f7c830bd89acc67ec4af516284b1bc33c', // EUROC
  '0xc581b735a1688071a1746c968e0798d642ede491', // EURT
  '0x0c10bf8fcb7bf5412187a595ab97a3609160b5c6', // USDD
  '0xa47c8bf37f92abed4a126bda807a7b7498661acd', // USTC
  '0xad3e3fc59dff318beceaab7d00eb4f68b1ecf195', // WCUSD
  '0x2a8e1e676ec238d8a992307b495b45b3feaa5e86'  // OUSD
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

/**
 * Classify pool type based on token addresses
 */
export function classifyPool(token0, token1) {
  const t0 = token0.toLowerCase();
  const t1 = token1.toLowerCase();

  const isToken0ETH = t0 === WETH;
  const isToken1ETH = t1 === WETH;
  const isToken0Stable = STABLECOINS.has(t0);
  const isToken1Stable = STABLECOINS.has(t1);

  if (isToken0ETH || isToken1ETH) {
    return 'eth_paired';
  } else if (isToken0Stable && isToken1Stable) {
    return 'stablecoin';
  } else {
    return 'other';
  }
}

/**
 * Fetch pool metadata (token addresses and fee)
 */
export async function fetchPoolMetadata(poolAddress) {
  try {
    const provider = await getProvider();
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
    console.error(`Failed to fetch pool metadata for ${poolAddress}:`, error.message);
    return null;
  }
}

/**
 * Fetch token metadata (symbol and decimals)
 */
export async function fetchTokenMetadata(tokenAddress) {
  try {
    const provider = await getProvider();
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

export { WETH, STABLECOINS };
