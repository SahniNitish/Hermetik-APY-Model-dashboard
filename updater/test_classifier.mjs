/**
 * Test Pool Classifier with 100 pools
 */

import { ethers } from 'ethers';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import dotenv from 'dotenv';
import { classifyAllPools } from './pool_classifier.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

dotenv.config({ path: path.join(__dirname, '.env') });

const OUTPUT_DIR = path.join(__dirname, 'static');

async function testClassifier() {
  console.log('🧪 Testing pool classifier with 100 sample pools...\n');

  // Read sample pools
  const poolsFile = path.join(OUTPUT_DIR, 'unique_pools_sample.txt');
  const poolAddresses = fs.readFileSync(poolsFile, 'utf8')
    .split('\n')
    .filter(addr => addr.trim().length > 0)
    .map(addr => addr.trim().toLowerCase());

  await classifyAllPools(poolAddresses);

  console.log('✅ Test complete! Check static/pool_metadata.csv\n');
  console.log('If this looks good, run the full classification:');
  console.log('  node pool_classifier.mjs\n');
}

testClassifier();
