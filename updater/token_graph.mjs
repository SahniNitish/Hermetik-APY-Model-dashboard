import fs from 'fs';
import path from 'path';
import yargs from 'yargs';
import { hideBin } from 'yargs/helpers';

const argv = yargs(hideBin(process.argv)).argv;
const inputCsv = argv['input'] || 'oneinch_logs.csv';
const outputCsv = argv['output'] || 'token_graph.csv';
const minTxns = Number(argv['min-txns'] || 10);

function parseCSV(csvContent) {
  const lines = csvContent.trim().split('\n');
  if (lines.length <= 1) return [];
  const header = lines[0].split(',');
  const idx = Object.fromEntries(header.map((h, i) => [h.trim(), i]));
  const rows = [];
  for (let i = 1; i < lines.length; i++) {
    const parts = lines[i].split(',');
    if (parts.length < 5) continue;
    rows.push({
      inputToken: parts[idx['Input Token']],
      outputToken: parts[idx['Output Token']],
      contract: parts[idx['Contract Address']]
    });
  }
  return rows;
}

function main() {
  const csvContent = fs.readFileSync(inputCsv, 'utf-8');
  const records = parseCSV(csvContent);
  const poolTxCount = new Map();
  const edges = new Map();

  for (const r of records) {
    if (!r.inputToken || !r.outputToken || !r.contract) continue;
    poolTxCount.set(r.contract, (poolTxCount.get(r.contract) || 0) + 1);
    const a = r.inputToken;
    const b = r.outputToken;
    if (!a || !b || a === b) continue;
    const key = [a, b].sort().join('::');
    if (!edges.has(key)) edges.set(key, new Set());
    edges.get(key).add(r.contract);
  }

  const rows = ['node1,node2,contract,label'];
  for (const [key, contracts] of edges) {
    for (const contract of contracts) {
      if ((poolTxCount.get(contract) || 0) < minTxns) continue;
      const [n1, n2] = key.split('::');
      rows.push(`${n1},${n2},${contract},UNKNOWN`);
    }
  }
  fs.writeFileSync(outputCsv, rows.join('\n'));
}

main();
