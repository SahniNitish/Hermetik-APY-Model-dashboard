const { ethers } = require("ethers");
const fs = require('fs');
const path = require('path');

// Try to load .env from current directory
require('dotenv').config();

const argv = require('yargs/yargs')(process.argv.slice(2)).argv;

if (!process.env.ALCHEMY_API_KEY) {
    console.error('Error: ALCHEMY_API_KEY not found in .env file');
    process.exit(1);
}

try {
    require.resolve('ethers');
    require.resolve('dotenv');
} catch (error) {
    console.error('Error: Required dependencies are missing. Please run:');
    console.error('npm install');
    process.exit(1);
}

const ALCHEMY_URL = `https://eth-mainnet.g.alchemy.com/v2/${process.env.ALCHEMY_API_KEY}`;
const provider = new ethers.JsonRpcProvider(ALCHEMY_URL);

// Known 1inch aggregator contracts
const KNOWN_CONTRACTS = new Set([
    "0x1111111254EEB25477B68fb85Ed929f73A960582",
    "0x111111125421cA6dc452d289314280a0f8842A65",
    "0x1111111254fb6c44bAC0beD2854e76F90643097d"
]);

// V4 PoolManager contract address (mainnet)
const UNISWAP_V4_POOL_MANAGER = "0x000000000004444c5dc75cB358380D2e3dE08A90";

const UNISWAP_V3_SWAP_TOPIC = "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67";
const UNISWAP_V2_SWAP_TOPIC = "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822";
const CURVE_SWAP_TOPIC = "0x8b3e96f2b889fa771c53c981b40daf005f63f637f1869f707052d15a3dd97140";
const UNISWAP_V4_SWAP_TOPIC = "0x40e9cecb9f5f1f1c5b9c97dec2917b7ee92e57ba5563708daca94dd84ad7112f";

const POOL_ABI_UNI = [
    "function token0() external view returns (address)",
    "function token1() external view returns (address)",
];

const CURVE_POOL_ABI_EXTENDED = [
    "function coins(uint256) external view returns (address)",
    "function coins(int128) external view returns (address)",
    "function underlying_coins(uint256) external view returns (address)", 
    "function underlying_coins(int128) external view returns (address)",
];

const BATCH_SIZE = 50;
const MAX_RETRIES = 3;
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

// Caching for pool tokens
const uniswapPoolTokenCache = new Map();
const curvePoolTokenCache = new Map();

async function retryableCall(fn, args = [], retries = MAX_RETRIES) {
    for (let i = 0; i < retries; i++) {
        try {
            return await fn(...args);
        } catch (e) {
            if (e.code === 429 && i < retries - 1) {
                await sleep(1000 * (i + 1));
            } else if (i === retries - 1) {
                return null;
            }
        }
    }
    return null;
}

// Uniswap V2 and V3
async function handleUniswapLog(log) {
    try {
        let tokens = uniswapPoolTokenCache.get(log.address);
        if (!tokens) {
            const pool = new ethers.Contract(log.address, POOL_ABI_UNI, provider);
            const token0 = await retryableCall(pool.token0.bind(pool));
            const token1 = await retryableCall(pool.token1.bind(pool));
            if (!token0 || !token1) return null;
            tokens = [token0, token1];
            uniswapPoolTokenCache.set(log.address, tokens);
        }
        const [token0, token1] = tokens;
        const data = ethers.dataSlice(log.data, 0);
        let decoded;
        try {
            decoded = ethers.AbiCoder.defaultAbiCoder().decode([
                "address", "address", "int256", "int256"
            ], data);
        } catch (error) {
            try {
                decoded = ethers.AbiCoder.defaultAbiCoder().decode([
                    "int256", "int256"
                ], data);
                return {
                    inputToken: token0,
                    outputToken: token1
                };
            } catch (innerError) {
                return null;
            }
        }
        const amount0 = decoded[2];
        const amount1 = decoded[3];
        const inputToken = amount0 < 0n ? token0 : token1;
        const outputToken = amount0 > 0n ? token0 : token1;
        return { inputToken, outputToken };
    } catch {
        return null;
    }
}

// Curve
async function handleCurveLog(log) {
    try {
        let tokens = curvePoolTokenCache.get(log.address);
        if (!tokens) {
            tokens = [];
            const pool = new ethers.Contract(log.address, CURVE_POOL_ABI_EXTENDED, provider);
            for (let i = 0; i < 8; i++) {
                let coin = null;
                for (const func of ['coins', 'underlying_coins']) {
                    for (const idx of [i, Number(i), BigInt(i)]) {
                        try {
                            coin = await retryableCall(pool[func].bind(pool), [idx]);
                            if (coin && ethers.isAddress(coin) && coin !== ethers.ZeroAddress) {
                                tokens[i] = coin;
                                break;
                            }
                        } catch (e) {}
                    }
                    if (tokens[i]) break;
                }
                if (!tokens[i]) break;
            }
            if (tokens.length === 0) return null;
            curvePoolTokenCache.set(log.address, tokens);
        }
        const data = ethers.dataSlice(log.data, 0);
        let decoded, soldId, boughtId;
        try {
            decoded = ethers.AbiCoder.defaultAbiCoder().decode([
                "int128", "uint256", "int128", "uint256"
            ], data);
            soldId = Number(decoded[0]);
            boughtId = Number(decoded[2]);
        } catch (error) {
            try {
                decoded = ethers.AbiCoder.defaultAbiCoder().decode([
                    "uint256", "uint256"
                ], data);
                soldId = 0;
                boughtId = 1;
            } catch (innerError) {
                return null;
            }
        }
        if (soldId < 0 || soldId >= tokens.length || boughtId < 0 || boughtId >= tokens.length) {
            return null;
        }
        const tokenIn = tokens[soldId];
        const tokenOut = tokens[boughtId];
        if (!tokenIn || !tokenOut || !ethers.isAddress(tokenIn) || !ethers.isAddress(tokenOut)) {
            return null;
        }
        return { inputToken: tokenIn, outputToken: tokenOut };
    } catch {
        return null;
    }
}

async function getLogs(fromBlock, toBlock, retries = 3) {
    try {
        let initialLogs;
        try {
            initialLogs = await provider.getLogs({
                fromBlock,
                toBlock,
                address: Array.from(KNOWN_CONTRACTS)
            });
        } catch (error) {
            if (retries > 0) {
                await sleep(1000);
                return getLogs(fromBlock, toBlock, retries - 1);
            }
            return [];
        }
        const txHashes = [...new Set(initialLogs.map(log => log.transactionHash))];
        const allLogs = [];
        for (let i = 0; i < txHashes.length; i += BATCH_SIZE) {
            const batch = txHashes.slice(i, i + BATCH_SIZE);
            const batchPromises = batch.map(async (txHash) => {
                try {
                    const receipt = await provider.getTransactionReceipt(txHash);
                    if (receipt && receipt.logs) {
                        return receipt.logs;
                    }
                    return [];
                } catch {
                    return [];
                }
            });
            const batchResults = await Promise.all(batchPromises);
            allLogs.push(...batchResults.flat());
        }
        const filteredLogs = allLogs.filter(log =>
            log.topics[0] && (
                log.topics[0] === UNISWAP_V3_SWAP_TOPIC ||
                log.topics[0] === UNISWAP_V2_SWAP_TOPIC ||
                log.topics[0] === CURVE_SWAP_TOPIC ||
                (log.topics[0] === UNISWAP_V4_SWAP_TOPIC && log.address === UNISWAP_V4_POOL_MANAGER)
            )
        );
        const processedLogs = [];
        for (let i = 0; i < filteredLogs.length; i += BATCH_SIZE) {
            const batch = filteredLogs.slice(i, i + BATCH_SIZE);
            const batchResults = await Promise.all(batch.map(async (log) => {
                let result = null;
                if (log.topics[0] === UNISWAP_V3_SWAP_TOPIC || log.topics[0] === UNISWAP_V2_SWAP_TOPIC) {
                    result = await handleUniswapLog(log);
                } else if (log.topics[0] === CURVE_SWAP_TOPIC) {
                    result = await handleCurveLog(log);
                } else if (log.address === UNISWAP_V4_POOL_MANAGER && log.topics[0] === UNISWAP_V4_SWAP_TOPIC) {
                    // Skip V4 in this minimal standalone
                    return null;
                }
                if (result && result.inputToken && result.outputToken) {
                    return {
                        transactionHash: log.transactionHash,
                        contractAddress: log.address,
                        inputToken: result.inputToken,
                        outputToken: result.outputToken,
                        blockNumber: log.blockNumber,
                        protocol: (log.topics[0] === UNISWAP_V3_SWAP_TOPIC) ? 'Uniswap V3' :
                                  (log.topics[0] === UNISWAP_V2_SWAP_TOPIC) ? 'Uniswap V2' : 'Curve',
                        poolId: '',
                        sender: '',
                        fee: ''
                    };
                }
                return null;
            }));
            processedLogs.push(...batchResults.filter(log => log !== null));
        }
        return processedLogs;
    } catch {
        return [];
    }
}

async function main() {
    try {
        const currentBlock = await provider.getBlockNumber();
        let fromBlock = argv['from-block'];
        let toBlock = argv['to-block'];
        let outputPath = argv['output'];
        if (!toBlock) toBlock = currentBlock;
        if (!fromBlock) fromBlock = toBlock - 7200;
        if (!outputPath) outputPath = path.join(process.cwd(), 'oneinch_logs.csv');
        console.log('Current block number:', currentBlock);
        console.log('Starting from block:', fromBlock);
        console.log('Ending block:', toBlock);
        console.log('Output path:', outputPath);
        
        let totalLogs = [];
        for (let i = fromBlock; i < toBlock; i += 500) {
            const endBlock = Math.min(i + 499, toBlock);
            console.log(`Fetching logs for blocks ${i} to ${endBlock}...`);
            const logs = await getLogs(i, endBlock);
            console.log(`Found ${logs.length} logs in this chunk`);
            totalLogs.push(...logs);
            await sleep(300);
        }
        if (totalLogs.length > 0) {
            try {
                fs.accessSync(path.dirname(outputPath), fs.constants.W_OK);
            } catch (error) {
                console.error(`Error: Cannot write to directory ${path.dirname(outputPath)}`);
                process.exit(1);
            }
            const headers = [
                "Transaction Hash",
                "Contract Address",
                "Input Token",
                "Output Token",
                "Block Number",
                "Protocol",
                "Pool ID",
                "Sender",
                "Fee"
            ];
            const csvContent = [
                headers.join(','),
                ...totalLogs.map(log =>
                    `${log.transactionHash},${log.contractAddress},${log.inputToken},${log.outputToken},${log.blockNumber},${log.protocol},${log.poolId || ''},${log.sender || ''},${log.fee || ''}`
                )
            ].join('\n');
            fs.writeFileSync(outputPath, csvContent);
            console.log(`\nSaved ${totalLogs.length} logs to ${outputPath}`);
        } else {
            console.log('\nNo logs found');
        }
    } catch (error) {
        console.error('Error in main:', error);
        process.exit(1);
    }
}

main();
