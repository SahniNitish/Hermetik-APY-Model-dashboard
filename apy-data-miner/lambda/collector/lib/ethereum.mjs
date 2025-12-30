/**
 * Ethereum Interaction Module
 * Handles all blockchain queries via Alchemy
 */

import { ethers } from 'ethers';
import { SecretsManagerClient, GetSecretValueCommand } from '@aws-sdk/client-secrets-manager';

// Uniswap V3 Swap event signature
const SWAP_EVENT_TOPIC = '0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67';

// Swap event ABI for parsing
const SWAP_EVENT_ABI = [
  'event Swap(address indexed sender, address indexed recipient, int256 amount0, int256 amount1, uint160 sqrtPriceX96, uint128 liquidity, int24 tick)'
];

let provider = null;
let swapInterface = null;

/**
 * Get Alchemy API key from Secrets Manager or environment
 */
async function getAlchemyApiKey() {
  // For local development
  if (process.env.ALCHEMY_API_KEY) {
    return process.env.ALCHEMY_API_KEY;
  }

  // For AWS Lambda - fetch from Secrets Manager
  const client = new SecretsManagerClient({ region: process.env.AWS_REGION || 'us-east-1' });

  const command = new GetSecretValueCommand({
    SecretId: process.env.SECRETS_ARN || 'apy-data-miner/alchemy'
  });

  const response = await client.send(command);
  const secrets = JSON.parse(response.SecretString);

  return secrets.ALCHEMY_API_KEY;
}

/**
 * Initialize Ethereum provider
 */
async function initProvider() {
  if (provider) return provider;

  const apiKey = await getAlchemyApiKey();
  provider = new ethers.JsonRpcProvider(
    `https://eth-mainnet.g.alchemy.com/v2/${apiKey}`
  );

  swapInterface = new ethers.Interface(SWAP_EVENT_ABI);

  console.log('Ethereum provider initialized');
  return provider;
}

/**
 * Get block range for the past N blocks
 */
export async function getBlockRange(blocksBack) {
  await initProvider();

  const currentBlock = await provider.getBlockNumber();
  const startBlock = currentBlock - blocksBack;

  return {
    startBlock,
    endBlock: currentBlock,
    currentBlock
  };
}

/**
 * Parse a swap log into structured data
 */
function parseSwapLog(log, timestamp) {
  try {
    const parsed = swapInterface.parseLog({
      topics: log.topics,
      data: log.data
    });

    return {
      blockNumber: log.blockNumber,
      timestamp,
      txHash: log.transactionHash,
      poolAddress: log.address.toLowerCase(),
      sender: parsed.args.sender.toLowerCase(),
      recipient: parsed.args.recipient.toLowerCase(),
      amount0: parsed.args.amount0.toString(),
      amount1: parsed.args.amount1.toString(),
      sqrtPriceX96: parsed.args.sqrtPriceX96.toString(),
      liquidity: parsed.args.liquidity.toString(),
      tick: parsed.args.tick.toString()
    };
  } catch (error) {
    return null;
  }
}

/**
 * Fetch swap logs for a block range
 */
export async function getSwapLogs(fromBlock, toBlock) {
  await initProvider();

  const logs = await provider.getLogs({
    fromBlock,
    toBlock,
    topics: [SWAP_EVENT_TOPIC]
  });

  if (logs.length === 0) {
    return [];
  }

  // Get timestamp from middle block
  const midBlock = Math.floor((fromBlock + toBlock) / 2);
  const block = await provider.getBlock(midBlock);
  const timestamp = new Date(block.timestamp * 1000).toISOString();

  // Parse all logs
  const parsedLogs = [];
  for (const log of logs) {
    const parsed = parseSwapLog(log, timestamp);
    if (parsed) {
      parsedLogs.push(parsed);
    }
  }

  return parsedLogs;
}

/**
 * Get provider instance (for other modules)
 */
export async function getProvider() {
  return initProvider();
}

export { SWAP_EVENT_TOPIC };
