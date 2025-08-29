import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { spawnSync } from 'child_process';
import { S3Client, PutObjectCommand } from '@aws-sdk/client-s3';
import yargs from 'yargs';
import { hideBin } from 'yargs/helpers';

const argv = yargs(hideBin(process.argv)).argv;

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const hourBlocks = 300; // ~1 hour
const timeframes = [
  { name: '1D', blocks: 7200 },
  { name: '3D', blocks: 21600 },
  { name: '1W', blocks: 50400 },
  { name: '3W', blocks: 151200 },
  { name: '1M', blocks: 302400 }
];

const chosenRegion = argv.region || process.env.AWS_REGION || process.env.AWS_DEFAULT_REGION || 'us-east-1';

function getFormattedDate() {
  const date = new Date();
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function parseCSV(csvContent) {
  const lines = csvContent.trim().split('\n');
  if (lines.length <= 1) return []; // No data or just header
  const txs = [];
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;
    const parts = line.split(',');
    if (parts.length === 9) {
      txs.push({
        hash: parts[0],
        contract: parts[1],
        inputToken: parts[2],
        outputToken: parts[3],
        blockNumber: Number(parts[4]),
        protocol: parts[5],
        poolId: parts[6],
        sender: parts[7],
        fee: parts[8],
        line
      });
    } else if (parts.length === 5) {
      txs.push({
        hash: parts[0],
        contract: parts[1],
        inputToken: parts[2],
        outputToken: parts[3],
        blockNumber: Number(parts[4]),
        protocol: 'Unknown',
        poolId: '',
        sender: '',
        fee: '',
        line
      });
    }
  }
  return txs;
}

function writeCSV(transactions, outputPath) {
  const hasV4Data = transactions.some(tx => tx.protocol && tx.protocol !== 'Unknown');
  const header = hasV4Data
    ? 'Transaction Hash,Contract Address,Input Token,Output Token,Block Number,Protocol,Pool ID,Sender,Fee'
    : 'Transaction Hash,Contract Address,Input Token,Output Token,Block Number';
  const lines = [header, ...transactions.map(tx => tx.line)];
  fs.writeFileSync(outputPath, lines.join('\n'));
  const size = fs.statSync(outputPath).size;
  console.log(`[done] wrote ${outputPath} (${size} bytes)`);
}

async function getCurrentBlock() {
  const { ethers } = await import('ethers');
  const ALCHEMY_API_KEY = process.env.ALCHEMY_API_KEY;
  if (!ALCHEMY_API_KEY) throw new Error('ALCHEMY_API_KEY not set');
  const provider = new ethers.JsonRpcProvider(`https://eth-mainnet.g.alchemy.com/v2/${ALCHEMY_API_KEY}`);
  const b = await provider.getBlockNumber();
  console.log(`[info] Current block: ${b}`);
  return b;
}

function runOneInchSwaps(fromBlock, toBlock, outPath) {
  console.log(`[run] oneinch_swaps from=${fromBlock} to=${toBlock} -> ${outPath}`);
  const script = path.join(__dirname, 'oneinch_swaps.cjs');
  const res = spawnSync('node', [script, '--from-block', String(fromBlock), '--to-block', String(toBlock), '--output', outPath], {
    cwd: __dirname,
    stdio: 'inherit'
  });
  if (res.status !== 0) {
    throw new Error(`oneinch_swaps failed with code ${res.status}`);
  }
}

function fetchNewTransactions(fromBlock, toBlock, tmpPath) {
  runOneInchSwaps(fromBlock, toBlock, tmpPath);
  if (!fs.existsSync(tmpPath)) {
    console.log(`[warn] no temp file produced for ${fromBlock}-${toBlock}`);
    return [];
  }
  const content = fs.readFileSync(tmpPath, 'utf-8');
  fs.unlinkSync(tmpPath);
  return parseCSV(content);
}

async function uploadFile(bucket, key, localPath) {
  const s3 = new S3Client({ region: chosenRegion });
  const body = fs.readFileSync(localPath);
  console.log(`[upload] region=${chosenRegion} s3://${bucket}/${key} (size=${body.length})`);
  await s3.send(new PutObjectCommand({ Bucket: bucket, Key: key, Body: body }));
  console.log(`[ok] uploaded ${key}`);
}

function updateTimeframeWithSlidingWindow(tf, currentBlock, staticDir) {
  console.log(`\n[tf] ${tf.name} sliding-window update`);
  const timeframeStartBlock = currentBlock - tf.blocks;
  const lastHourStartBlock = timeframeStartBlock - hourBlocks;
  const lastHourEndBlock = timeframeStartBlock;
  const newHourStartBlock = currentBlock - hourBlocks;
  const newHourEndBlock = currentBlock;

  const logsFile = path.join(staticDir, `oneinch_logs_${tf.name}.csv`);

  let existing = [];
  if (fs.existsSync(logsFile)) {
    const existingContent = fs.readFileSync(logsFile, 'utf-8');
    existing = parseCSV(existingContent);
    console.log(`[tf:${tf.name}] existing txns: ${existing.length}`);
  } else {
    console.log(`[tf:${tf.name}] no existing file; will fetch full range initially`);
    const tmpInit = path.join(staticDir, `tmp_init_${tf.name}.csv`);
    const initTxns = fetchNewTransactions(timeframeStartBlock, currentBlock, tmpInit);
    writeCSV(initTxns, logsFile);
    return initTxns.length;
  }

  // Remove last hour of the previous window
  const filtered = existing.filter(tx => tx.blockNumber < lastHourStartBlock || tx.blockNumber >= lastHourEndBlock);
  console.log(`[tf:${tf.name}] removed ${existing.length - filtered.length} from last hour`);

  // Fetch new hour
  const tmpNew = path.join(staticDir, `tmp_new_${tf.name}.csv`);
  const newTxns = fetchNewTransactions(newHourStartBlock, newHourEndBlock, tmpNew);
  console.log(`[tf:${tf.name}] fetched new hour: ${newTxns.length}`);

  // Deduplicate by hash
  const seen = new Set(newTxns.map(t => t.hash));
  const kept = filtered.filter(tx => !seen.has(tx.hash));
  const all = [...kept, ...newTxns];
  console.log(`[tf:${tf.name}] final: ${all.length} (kept ${kept.length} + new ${newTxns.length})`);

  writeCSV(all, logsFile);
  return all.length;
}

function buildGraphForTimeframe(tf, staticDir) {
  const logsFile = path.join(staticDir, `oneinch_logs_${tf.name}.csv`);
  if (!fs.existsSync(logsFile)) {
    console.log(`[graph:${tf.name}] logs file missing, skipping`);
    return null;
  }
  const content = fs.readFileSync(logsFile, 'utf-8');
  const txns = parseCSV(content);
  const total = txns.length;
  const minTxns = Math.max(1, Math.floor(total * 0.02));
  const outGraph = path.join(staticDir, `token_graph${tf.name}.csv`);
  console.log(`[graph:${tf.name}] total=${total} minTxns=${minTxns}`);
  const res = spawnSync('node', ['token_graph.mjs', '--input', logsFile, '--min-txns', String(minTxns), '--output', outGraph], {
    cwd: __dirname,
    stdio: 'inherit'
  });
  if (res.status !== 0) {
    console.log(`[graph:${tf.name}] generation failed`);
    return null;
  }
  console.log(`[graph:${tf.name}] wrote ${outGraph}`);
  return outGraph;
}

async function main() {
  const bucket = argv.bucket;
  const noUpload = Boolean(argv['no-upload']);
  if (!bucket && !noUpload) {
    console.error('--bucket is required (or pass --no-upload)');
    process.exit(1);
  }

  console.log(`[info] Using AWS region: ${chosenRegion}`);

  const staticDir = path.join(__dirname, 'static');
  const dailyLogsDir = path.join(staticDir, 'daily_logs');
  const dailyGraphsDir = path.join(staticDir, 'daily_graphs');
  fs.mkdirSync(staticDir, { recursive: true });
  fs.mkdirSync(dailyLogsDir, { recursive: true });
  fs.mkdirSync(dailyGraphsDir, { recursive: true });

  const currentBlock = await getCurrentBlock();

  // Update rolling files via sliding window
  for (const tf of timeframes) {
    updateTimeframeWithSlidingWindow(tf, currentBlock, staticDir);
    const graphPath = buildGraphForTimeframe(tf, staticDir);
    if (!noUpload) {
      const logFile = path.join(staticDir, `oneinch_logs_${tf.name}.csv`);
      if (fs.existsSync(logFile)) {
        await uploadFile(bucket, `rolling/oneinch_logs_${tf.name}.csv`, logFile);
      }
      if (graphPath && fs.existsSync(graphPath)) {
        await uploadFile(bucket, `rolling/${path.basename(graphPath)}`, graphPath);
      }
    }
  }

  // Build daily snapshot (today) from last 1D rolling file
  const dateStr = getFormattedDate();
  const dailyOut = path.join(dailyLogsDir, `${dateStr}-oneinch_logs.csv`);
  const oneDayLogs = path.join(staticDir, 'oneinch_logs_1D.csv');
  if (fs.existsSync(oneDayLogs)) {
    fs.copyFileSync(oneDayLogs, dailyOut);
    console.log(`[daily] copied ${oneDayLogs} -> ${dailyOut}`);
    if (!noUpload) {
      await uploadFile(bucket, `logs/${path.basename(dailyOut)}`, dailyOut);
    }
  } else {
    console.log('[daily] missing oneinch_logs_1D.csv; skipping daily log upload');
  }

  // Daily graph from 1D rolling graph if present
  const dailyGraphLocal = path.join(dailyGraphsDir, `${dateStr}-token_graph.csv`);
  const rollingGraphCandidate = path.join(staticDir, `token_graph1D.csv`);
  if (fs.existsSync(rollingGraphCandidate)) {
    fs.copyFileSync(rollingGraphCandidate, dailyGraphLocal);
    console.log(`[daily-graph] copied ${rollingGraphCandidate} -> ${dailyGraphLocal}`);
    if (!noUpload) {
      await uploadFile(bucket, `graphs/${path.basename(dailyGraphLocal)}`, dailyGraphLocal);
    }
  } else {
    console.log('[daily-graph] rolling token_graph1D.csv not found; skipping daily graph upload');
  }

  console.log('Updater finished');
}

main().catch(err => {
  console.error('[error]', err);
  process.exit(1);
});
