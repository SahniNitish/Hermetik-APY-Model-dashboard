# 📘 Complete Technical Documentation - Pool Performance Prediction Pipeline

**Project:** Transform DeFi liquidity classification model → Pool performance prediction model
**Date:** November 2, 2025
**Status:** ✅ ALL 5 PHASES COMPLETE
**Your Role:** Data Pipeline (collecting & preparing data)
**Nolan's Role:** Model Training & Prediction

---

## 🎯 PROJECT GOAL

### Original Request
You and your friend Nolan are working on a DeFi prediction model as a group project:
- **Your job:** Fetch and prepare data for the last 30 days
- **Nolan's job:** Train a model to predict which pools will perform best in the future

### What Changed From Original Setup
**BEFORE (Old Model):**
- Predicted: Binary classification (high liquidity YES/NO)
- Pools: Only ETH pools (ETH/USDC, ETH/DAI, etc.)
- Data: Single snapshot in time
- Target: Binary label (1 or 0)

**AFTER (New Model - What We Built):**
- Predicts: Future transaction activity (regression, continuous value)
- Pools: ALL pool types (ETH + stablecoins + other tokens)
- Data: 30-day time-series (daily snapshots)
- Target: Future transaction count (proxy for pool performance/APY)

### Why This Approach?
1. **Transaction count = Performance proxy:** More transactions → More fees → Higher APY
2. **Easier to predict:** Transaction patterns are more stable than APY calculations
3. **No need for complex APY math:** Don't need to fetch reserves/prices in real-time
4. **Works for all pool types:** Can compare ETH pools vs stablecoins vs others

---

## 📋 PHASES COMPLETED (Overview)

| Phase | What | Why | Time |
|-------|------|-----|------|
| **Phase 1** | Collect 7.2M transactions (30 days) | Need historical data for training | 25 min |
| **Phase 2** | Classify 6,105 pools by type | Different pool types behave differently | 15 min |
| **Phase 3** | Generate time-series features | Create input features for model | 2 min |
| **Phase 4** | Create train/test datasets | Prepare data for Nolan's model | 1 min |
| **Phase 5** | Documentation & packaging | Help Nolan understand and use data | 5 min |

---

## 🔧 PHASE 1: DATA COLLECTION (30 Days)

### What We Did
Collected 30 days of historical swap transaction data from Ethereum blockchain.

### Why
- Need historical patterns to predict future behavior
- 30 days gives enough data for trends (7-day averages, etc.)
- More data = better model training

### How (Technical Details)

#### 1.1 Technology Stack
- **Alchemy API:** Ethereum node provider (faster than public RPC)
- **Node.js + ethers.js:** To query blockchain
- **Uniswap V3 Swap Events:** Filter for swap transactions

#### 1.2 Key Script: `updater/historical_collector_v2.mjs`

**What it does:**
```javascript
1. Calculate block range (current block - 216,000 blocks = ~30 days)
2. Fetch swap events in batches of 1,000 blocks
3. Parse transaction data (pool address, amounts, sender, recipient)
4. Save to CSV in real-time (memory-efficient)
5. Add 1-second delay between batches (avoid rate limits)
```

**Key Configuration:**
```javascript
BLOCKS_PER_DAY = 7200        // Ethereum: ~12 sec/block
DAYS_TO_FETCH = 30           // 30 days back
TOTAL_BLOCKS = 216,000       // 7200 × 30
BATCH_SIZE = 1000            // Process 1000 blocks at a time
DELAY_MS = 800               // 0.8 sec between batches
```

**Event We Track:**
```javascript
SWAP_EVENT_TOPIC = '0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67'
// This is the Uniswap V3 Swap event signature
```

#### 1.3 How to Run It
```bash
# From project root
cd updater
node historical_collector_v2.mjs 30

# Or specify different number of days:
node historical_collector_v2.mjs 7   # Last 7 days
node historical_collector_v2.mjs 60  # Last 60 days
```

#### 1.4 Output
- **File:** `updater/static/pool_logs_30d_2025-11-02.csv`
- **Size:** 2.2 GB
- **Rows:** 7,188,733 transactions
- **Columns:**
  - `blockNumber` - Ethereum block number
  - `timestamp` - ISO datetime string
  - `txHash` - Transaction hash
  - `poolAddress` - Uniswap V3 pool contract
  - `sender` - Wallet initiating swap
  - `recipient` - Wallet receiving tokens
  - `amount0` - Token0 amount (can be negative)
  - `amount1` - Token1 amount (can be negative)
  - `sqrtPriceX96` - Pool price after swap
  - `liquidity` - Pool liquidity
  - `tick` - Price tick

#### 1.5 Key Decisions
- **Why memory-efficient approach?** Large files (2GB+) crash if loaded in memory
- **Why 1-second delay?** Alchemy free tier: 330 CU/sec, need to stay under limit
- **Why save incrementally?** If script crashes, we don't lose all data

#### 1.6 Troubleshooting
**Problem:** "Out of memory" error
**Solution:** We write to CSV incrementally, never load full dataset in memory

**Problem:** Rate limit errors
**Solution:** Increase `DELAY_MS` to 1000 or 1500

**Problem:** Some pools fail to fetch
**Solution:** Normal - some pool addresses are invalid/old contracts, we skip them

---

## 🔧 PHASE 2: POOL CLASSIFICATION

### What We Did
Classified 6,131 unique pools into 3 categories: ETH-paired, stablecoins, other tokens.

### Why
Different pool types have different behavior patterns:
- **ETH pools:** Volatile, high transaction volume, sensitive to ETH price
- **Stablecoin pools:** Stable, low fees, high volume, predictable
- **Other pools:** Mixed behavior, often illiquid, high variance

Models can learn these patterns better if we label the pool type.

### How (Technical Details)

#### 2.1 Extract Unique Pools
```bash
# From raw transaction data, get unique pool addresses
tail -n +2 static/pool_logs_30d_2025-11-02.csv | cut -d',' -f4 | sort -u > static/unique_pools.txt

# Result: 6,131 unique pool addresses
```

#### 2.2 Key Script: `updater/pool_classifier.mjs`

**What it does:**
```javascript
1. For each pool address:
   a. Call pool.token0() - get first token address
   b. Call pool.token1() - get second token address
   c. Call pool.fee() - get fee tier (500, 3000, 10000)
   d. Call token0.symbol() - get token symbol (USDC, ETH, etc.)
   e. Call token1.symbol() - get token symbol
   f. Classify based on tokens:
      - If either token is WETH → "eth_paired"
      - If both are stablecoins → "stablecoin"
      - Otherwise → "other"
2. Save to CSV with pool metadata
```

**Classification Logic:**
```javascript
const WETH = '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2';
const STABLECOINS = [
  '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',  // USDC
  '0xdac17f958d2ee523a2206206994597c13d831ec7',  // USDT
  '0x6b175474e89094c44da98b954eedeac495271d0f',  // DAI
  '0x853d955acef822db058eb8505911ed77f175b99e',  // FRAX
  '0x5f98805a4e8be255a32880fdec7f6728c6568ba0',  // LUSD
  '0x4fabb145d64652a948d72533023f6e7a623c7c53'   // BUSD
];

function classifyPool(token0, token1) {
  if (token0 === WETH || token1 === WETH) {
    return 'eth_paired';
  } else if (STABLECOINS.includes(token0) && STABLECOINS.includes(token1)) {
    return 'stablecoin';
  } else {
    return 'other';
  }
}
```

#### 2.3 How to Run It
```bash
cd updater

# Test with 100 pools first:
node test_classifier.mjs

# Run full classification:
node pool_classifier.mjs
```

#### 2.4 Output
- **File:** `updater/static/pool_metadata.csv`
- **Rows:** 6,105 pools (26 failed = invalid contracts)
- **Columns:**
  - `poolAddress` - Pool contract address
  - `token0` - First token address
  - `token1` - Second token address
  - `token0Symbol` - Token symbol (USDC, WETH, etc.)
  - `token1Symbol` - Token symbol
  - `fee` - Fee tier (500, 3000, 10000)
  - `poolType` - Classification (eth_paired, stablecoin, other)

**Example Row:**
```csv
0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640,0xa0b86991...,0xc02aaa39...,USDC,WETH,500,eth_paired
```

#### 2.5 Results
- **ETH-paired pools:** 4,350 (71.3%)
- **Stablecoin pools:** 25 (0.4%)
- **Other token pools:** 1,730 (28.3%)
- **Failed:** 26 (0.4% - normal, invalid contracts)

#### 2.6 Key Decisions
- **Why batch processing?** Avoid rate limits, process 50 pools at once
- **Why these stablecoins?** Most common on Uniswap V3
- **Why 500ms delay?** Balance between speed and rate limits

---

## 🔧 PHASE 3: TIME-SERIES FEATURE GENERATION

### What We Did
Transformed raw transaction logs into daily time-series features for each pool.

### Why
Machine learning models need **features** (input variables), not raw transactions.

We create features like:
- How many transactions did this pool have **today**?
- What's the **7-day average** transaction count?
- Is the pool **growing or shrinking**?
- How **volatile** is the activity?

### How (Technical Details)

#### 3.1 Key Script: `generate_timeseries_features.py`

**What it does:**
```python
1. Load 7.2M transactions from CSV (in chunks to save memory)
2. Extract date from timestamp
3. Group by (pool, date) to get daily aggregates
4. For each pool:
   a. Count transactions per day
   b. Count unique users per day
   c. Calculate rolling averages (3-day, 7-day)
   d. Calculate volatility (7-day std dev)
   e. Calculate growth rate (vs previous day)
   f. Calculate cumulative totals
5. Save as time-series dataset (multiple rows per pool)
```

#### 3.2 Feature Engineering Details

**Daily Aggregates:**
```python
# Group all transactions by pool and date
daily_stats = logs_df.groupby(['poolAddress', 'date']).agg({
    'txHash': 'count',        # How many transactions
    'sender': 'nunique'       # How many unique wallets
}).reset_index()
```

**Rolling Windows:**
```python
# 3-day moving average
tx_count_3d_avg = group['tx_count'].rolling(window=3, min_periods=1).mean()

# 7-day moving average
tx_count_7d_avg = group['tx_count'].rolling(window=7, min_periods=1).mean()

# 7-day volatility (standard deviation)
tx_count_7d_std = group['tx_count'].rolling(window=7, min_periods=1).std()
```

**Growth Rate:**
```python
# Percent change from yesterday
tx_growth_rate = group['tx_count'].pct_change()
# Example: yesterday=100 txs, today=120 txs → growth_rate = 0.20 (20% increase)
```

#### 3.3 How to Run It
```bash
# From project root
source updater/venv/bin/activate
python generate_timeseries_features.py
```

#### 3.4 Output
- **File:** `pool_timeseries_features.csv`
- **Size:** 9.6 MB
- **Rows:** 61,798 (pool-day combinations)
- **Unique pools:** 6,131
- **Date range:** Oct 2 - Nov 2, 2025 (32 days)

**Columns (17 total):**
```
poolAddress           - Pool contract address
date                  - Date (YYYY-MM-DD)
pool_name             - Human-readable name (USDC/WETH)
token0Symbol          - First token
token1Symbol          - Second token
fee                   - Fee tier
fee_percentage        - Fee as decimal (0.003 = 0.3%)
poolType              - eth_paired, stablecoin, or other
tx_count              - Transactions this day
unique_users          - Unique wallets this day
tx_count_3d_avg       - 3-day rolling average
tx_count_7d_avg       - 7-day rolling average
tx_count_7d_std       - 7-day volatility
tx_count_cumulative   - Total transactions since start
days_since_start      - Days since first transaction
tx_growth_rate        - Growth rate vs yesterday
day_number            - Day sequence number (1-30)
```

**Example Rows (USDC/WETH pool):**
```csv
poolAddress,date,pool_name,tx_count,tx_count_7d_avg,day_number
0x88e6...,2025-10-02,USDC/WETH,3245,3245.0,1
0x88e6...,2025-10-03,USDC/WETH,3512,3378.5,2
0x88e6...,2025-10-04,USDC/WETH,3289,3348.7,3
...
0x88e6...,2025-11-02,USDC/WETH,3645,3421.4,32
```

#### 3.5 Key Decisions
- **Why rolling averages?** Smooth out daily noise, reveal trends
- **Why 7-day window?** 7 days captures weekly patterns (weekday/weekend)
- **Why growth rate?** Captures momentum (is pool trending up/down?)
- **Why process in chunks?** 7.2M rows too big for memory at once

#### 3.6 Data Quality Notes
- Some pools don't have 30 consecutive days (normal - new pools, inactive periods)
- Only 237 pools have full 30 days
- But 1,526 pools have 20+ days (still useful)
- Average: 10.1 days per pool

---

## 🔧 PHASE 4: CREATE TRAINING DATASET

### What We Did
Added **target variables** (what we want to predict) and split data into train/test sets.

### Why
For supervised learning, we need:
- **X (features):** Input data (what the model sees)
- **y (target):** What we want to predict (future transaction count)

Without targets, Nolan can't train a model.

### How (Technical Details)

#### 4.1 Key Script: `create_training_dataset.py`

**What it does:**
```python
1. Load time-series features (61,798 rows)
2. For each pool, create targets by shifting data:
   - target_tx_3d_ahead = tx_count shifted 3 days forward
   - target_tx_7d_ahead = tx_count shifted 7 days forward
   - target_tx_3d_avg_ahead = average of next 3 days
   - target_tx_7d_avg_ahead = average of next 7 days
3. Remove rows where target = NaN (last few days have no future data)
4. Split by date:
   - Training: Days 1-25 (Oct 2 - Oct 26)
   - Testing: Days 26-32 (Oct 27 - Nov 2)
5. Save separate CSV files
```

#### 4.2 Target Creation (The Magic)

**Concept:**
```
If today is Oct 5:
  - Current tx_count = 1,000 transactions
  - 7 days later (Oct 12) = 1,200 transactions
  - Therefore, target_tx_7d_ahead = 1,200

The model learns: "When I see these features on Oct 5,
the pool will have 1,200 txs on Oct 12"
```

**Code:**
```python
def add_target_variables(group):
    # Shift by -3 means "look 3 rows ahead"
    group['target_tx_3d_ahead'] = group['tx_count'].shift(-3)
    group['target_tx_7d_ahead'] = group['tx_count'].shift(-7)

    # Rolling average of future values
    group['target_tx_7d_avg_ahead'] = (
        group['tx_count']
        .shift(-7)
        .rolling(window=7, min_periods=1)
        .mean()
    )
    return group
```

**Why shift is negative:** Shift(-7) moves data UP (into past rows = future for those rows)

**Example:**
```
Row | Date    | tx_count | shift(-7) = target_tx_7d_ahead
----|---------|----------|--------------------------------
1   | Oct 1   | 100      | 150  (Oct 8's value)
2   | Oct 2   | 110      | 160  (Oct 9's value)
...
25  | Oct 25  | 130      | NaN  (Nov 1 doesn't exist)
26  | Oct 26  | 140      | NaN
```

#### 4.3 Train/Test Split Strategy

**Date-based split (NOT random!):**
```python
test_cutoff_date = max_date - timedelta(days=6)  # Last 7 days

train_df = df[df['date'] < test_cutoff_date]   # Oct 2 - Oct 26
test_df = df[df['date'] >= test_cutoff_date]   # Oct 27 - Nov 2
```

**Why date-based?** Time-series data has temporal dependency - can't shuffle randomly or we'd leak future into past.

**Why last 7 days for testing?** Simulates real-world: train on past, predict future.

#### 4.4 How to Run It
```bash
source updater/venv/bin/activate
python create_training_dataset.py
```

#### 4.5 Output Files

**1. pool_training_data.csv**
- **Rows:** 37,112
- **Pools:** 2,333
- **Date range:** Oct 2 - Oct 26
- **Use:** Train Nolan's model
- **Has:** Complete features + valid targets

**2. pool_test_data.csv**
- **Rows:** 11,826
- **Pools:** 3,330
- **Date range:** Oct 27 - Nov 2
- **Use:** Validate model performance
- **Note:** Some targets are NaN (no future data beyond Nov 2)

**3. pool_full_dataset.csv**
- **Rows:** 61,798 (everything)
- **Use:** Reference, analysis
- **Note:** Includes NaN targets

#### 4.6 Target Variable Comparison

| Target | What It Predicts | Best Use Case |
|--------|------------------|---------------|
| `target_tx_3d_ahead` | Exact count 3 days from now | Short-term prediction |
| `target_tx_7d_ahead` | Exact count 7 days from now | Medium-term prediction |
| `target_tx_3d_avg_ahead` | Average over next 3 days | Smoother short-term |
| `target_tx_7d_avg_ahead` | Average over next 7 days | **RECOMMENDED** (least noisy) |

**Recommendation for Nolan:** Use `target_tx_7d_avg_ahead` - it's smoother and more stable.

#### 4.7 Key Decisions
- **Why remove NaN targets from training?** Can't train on missing values
- **Why keep NaN in test set?** Can still predict for early days (Oct 27-28)
- **Why 4 different targets?** Nolan can choose based on use case

---

## 🔧 PHASE 5: DOCUMENTATION & PACKAGING

### What We Did
Created comprehensive documentation so Nolan can use the data immediately.

### Why
Without docs, Nolan would need to:
- Reverse-engineer what each column means
- Figure out which file to use
- Write his own training code from scratch
- Not understand why certain decisions were made

Good documentation = Nolan can start in 5 minutes.

### Files Created

#### 5.1 DATA_FOR_NOLAN.md (Main Guide)
**What it contains:**
- Dataset overview and stats
- Complete feature descriptions
- Quick-start code (copy-paste ready)
- Model training example
- Expected performance metrics
- Tips for improvement
- FAQ section

**Key sections:**
```markdown
1. Goal - What to predict
2. Files - What each file is
3. Features - Input variables explained
4. Targets - Output variables explained
5. Quick Start - Working code example
6. Expected Performance - Baseline metrics
7. Top Pools - Reference data
8. Tips - How to improve model
9. FAQ - Common questions
```

#### 5.2 PROJECT_COMPLETE_SUMMARY.md
**What it contains:**
- High-level summary
- What was accomplished
- Files for Nolan
- Next steps
- Success criteria

#### 5.3 TECHNICAL_DOCUMENTATION.md (This File)
**What it contains:**
- Complete technical details
- Every phase explained
- Why decisions were made
- How to run everything
- Troubleshooting
- Future improvements

---

## 📊 COMPLETE FILE STRUCTURE

```
caduceus-model/
├── 📁 updater/
│   ├── 📁 static/
│   │   ├── pool_logs_30d_2025-11-02.csv     (2.2 GB - Raw transactions)
│   │   ├── pool_metadata.csv                (Pool info - tokens, fees)
│   │   └── unique_pools.txt                 (6,131 pool addresses)
│   ├── 📁 venv/                             (Python virtual environment)
│   ├── .env                                  (ALCHEMY_API_KEY stored here)
│   ├── historical_collector_v2.mjs           ⭐ PHASE 1 SCRIPT
│   ├── pool_classifier.mjs                   ⭐ PHASE 2 SCRIPT
│   └── test_classifier.mjs                   (Test with 100 pools)
│
├── 📊 DATA FILES FOR NOLAN:
│   ├── pool_training_data.csv               ⭐⭐⭐ MAIN FILE (37K rows)
│   ├── pool_test_data.csv                   ⭐⭐⭐ VALIDATION (12K rows)
│   ├── pool_full_dataset.csv                (Complete 62K rows)
│   └── pool_timeseries_features.csv         (Features without targets)
│
├── 🐍 PYTHON SCRIPTS:
│   ├── generate_timeseries_features.py      ⭐ PHASE 3 SCRIPT
│   └── create_training_dataset.py           ⭐ PHASE 4 SCRIPT
│
├── 📖 DOCUMENTATION FOR NOLAN:
│   ├── DATA_FOR_NOLAN.md                    ⭐⭐⭐ MAIN GUIDE (give to Nolan)
│   ├── PROJECT_COMPLETE_SUMMARY.md          (Quick summary)
│   └── TECHNICAL_DOCUMENTATION.md           ⭐ THIS FILE (for you/me)
│
└── 📖 OTHER DOCS:
    ├── README_APY_MODEL.md                  (Original plan)
    ├── QUICKSTART.md                        (Quick start guide)
    ├── FEATURES.md                          (Feature descriptions)
    ├── HOW_TO_RUN.md                        (How to run old setup)
    ├── PHASE_2_SUMMARY.md                   (Phase 2 details)
    └── DATABASE_GUIDE.md                    (Database connection guide)
```

---

## 🎓 KEY CONCEPTS EXPLAINED

### 1. Why Time-Series Format?

**Traditional ML Dataset (Wrong for our case):**
```csv
pool,feature1,feature2,target
Pool_A,100,5,12.5
Pool_B,200,8,18.2
```
Each row = one pool, predict one value.

**Time-Series Dataset (What we built):**
```csv
pool,date,feature1,feature2,target_7d_ahead
Pool_A,Oct_1,100,5,120
Pool_A,Oct_2,110,6,125
Pool_A,Oct_3,105,5,115
Pool_B,Oct_1,200,8,210
Pool_B,Oct_2,220,9,230
```
Each row = one pool on one day, can see trends over time.

**Why this is better:**
- Captures temporal patterns (trends, seasonality)
- Can see if pool is growing or shrinking
- More training examples (30 rows per pool vs 1)

### 2. Why Rolling Averages?

**Raw data (noisy):**
```
Day 1: 100 txs
Day 2: 300 txs  ← Spike (maybe one big trader)
Day 3: 110 txs
Day 4: 105 txs
```

**7-day average (smooth):**
```
Day 1: 100
Day 2: 200  (average of 100, 300)
Day 3: 170  (average of 100, 300, 110)
Day 4: 154  (average of 100, 300, 110, 105)
```

**Benefit:** Model sees underlying trend, not random spikes.

### 3. Why Predict Transaction Count Instead of APY?

**APY Calculation is Complex:**
```
APY = (Fee_Revenue / TVL) × 365 × 100

Where:
  Fee_Revenue = Volume × Fee_Percentage
  TVL = Current pool reserves in USD

Requires:
  - Real-time token prices
  - Pool reserve amounts
  - Complicated on-chain queries
```

**Transaction Count is Simple:**
```
Just count: How many swaps happened?

Benefits:
  - Easy to calculate from logs
  - Strong correlation with APY (more txs = more fees)
  - More stable/predictable
  - Can be counted directly from data we already have
```

### 4. Train/Test Split for Time-Series

**WRONG (Random split):**
```
Training: Oct 1, Oct 15, Oct 3, Oct 22, ...
Testing:  Oct 8, Oct 2, Oct 19, ...

Problem: Model sees future data before training!
```

**CORRECT (Date-based split):**
```
Training: Oct 1 through Oct 26 (all data before cutoff)
Testing:  Oct 27 through Nov 2 (all data after cutoff)

Simulates: Train on past, predict future
```

---

## 🔄 HOW TO RUN ENTIRE PIPELINE AGAIN

### Prerequisites
```bash
# 1. Alchemy API key in .env files
echo "ALCHEMY_API_KEY=your_key_here" > .env
echo "ALCHEMY_API_KEY=your_key_here" > updater/.env

# 2. Node.js packages installed
cd updater && npm install

# 3. Python virtual environment
python3 -m venv updater/venv
source updater/venv/bin/activate
pip install pandas numpy scikit-learn networkx boto3 web3
```

### Run All Phases
```bash
# PHASE 1: Collect 30 days (25 minutes)
cd updater
node historical_collector_v2.mjs 30
# Output: static/pool_logs_30d_YYYY-MM-DD.csv

# PHASE 2: Classify pools (15 minutes)
node pool_classifier.mjs
# Output: static/pool_metadata.csv

# PHASE 3: Generate features (2 minutes)
cd ..
source updater/venv/bin/activate
python generate_timeseries_features.py
# Output: pool_timeseries_features.csv

# PHASE 4: Create training sets (1 minute)
python create_training_dataset.py
# Output: pool_training_data.csv, pool_test_data.csv, pool_full_dataset.csv

# Done! Give these 3 files to Nolan:
# - pool_training_data.csv
# - pool_test_data.csv
# - DATA_FOR_NOLAN.md
```

### Run Individual Phases

**Just re-collect data:**
```bash
cd updater
node historical_collector_v2.mjs 30
```

**Just re-classify pools:**
```bash
cd updater
node pool_classifier.mjs
```

**Just regenerate features:**
```bash
source updater/venv/bin/activate
python generate_timeseries_features.py
```

**Just regenerate training sets:**
```bash
source updater/venv/bin/activate
python create_training_dataset.py
```

---

## 🐛 TROUBLESHOOTING

### Phase 1 Issues

**Problem:** "Out of memory" error during collection
```bash
# Solution: Script already handles this by writing incrementally
# If still fails, reduce BATCH_SIZE in historical_collector_v2.mjs
# Change: BATCH_SIZE = 1000 → BATCH_SIZE = 500
```

**Problem:** "Rate limit exceeded"
```bash
# Solution: Increase delay between requests
# In historical_collector_v2.mjs:
# Change: DELAY_MS = 800 → DELAY_MS = 1500
```

**Problem:** "Cannot find module 'ethers'"
```bash
# Solution: Install dependencies
cd updater && npm install
```

### Phase 2 Issues

**Problem:** Many pools fail to classify
```bash
# This is normal! Some pools are:
# - Old/deprecated contracts
# - Not actually Uniswap V3 pools
# - Malformed addresses
#
# Expected failure rate: ~0.5-1%
# Current: 26/6131 = 0.4% ✅
```

**Problem:** Classification takes too long
```bash
# Solution: Reduce BATCH_SIZE in pool_classifier.mjs
# Change: BATCH_SIZE = 50 → BATCH_SIZE = 20
# Trade-off: Slower but safer for rate limits
```

### Phase 3 Issues

**Problem:** "ModuleNotFoundError: No module named 'pandas'"
```bash
# Solution: Activate virtual environment
source updater/venv/bin/activate
pip install pandas numpy
```

**Problem:** Script runs out of memory
```bash
# Solution: Reduce chunk_size in generate_timeseries_features.py
# Change: chunk_size = 500000 → chunk_size = 250000
```

**Problem:** "Can only use .dt accessor with datetimelike values"
```bash
# Solution: Already fixed in current version
# Make sure you're using latest generate_timeseries_features.py
```

### Phase 4 Issues

**Problem:** Too few training examples
```bash
# Check: How many pools have enough days?
python -c "
import pandas as pd
df = pd.read_csv('pool_timeseries_features.csv')
print(df.groupby('poolAddress').size().describe())
"

# If mean < 7, you might need more data collection days
```

**Problem:** Targets are mostly NaN
```bash
# This is expected for last 7 days
# Only matters for training set
# Check training set: should have NO NaN targets
python -c "
import pandas as pd
df = pd.read_csv('pool_training_data.csv')
print('NaN targets:', df['target_tx_7d_ahead'].isna().sum())
"
# Should be 0
```

---

## 🚀 WHAT'S NEXT (Future Improvements)

### For You (Data Pipeline)

**1. Automate Daily Updates**
```bash
# Create cron job to collect data daily
# Add to crontab:
0 2 * * * cd /path/to/updater && node collect_daily.mjs

# Create collect_daily.mjs:
# - Fetch last 24 hours only
# - Append to existing dataset
# - Regenerate features
# - Update training files
```

**2. Add More Features**
```python
# In generate_timeseries_features.py, add:

# Day of week (pools behave differently on weekends)
df['day_of_week'] = pd.to_datetime(df['date']).dt.dayofweek

# Hour of day (if we collect hourly data)
df['hour'] = pd.to_datetime(df['timestamp']).dt.hour

# Price volatility (would need price data)
# Token volume in USD (would need prices)
# Gas price correlation
```

**3. Collect Actual APY Data**
```javascript
// If you want real APY instead of transaction proxy:
// In pool_state_fetcher.mjs, add:

async function calculateAPY(poolAddress) {
  // Get pool reserves
  const token0Balance = await getTokenBalance(pool, token0);
  const token1Balance = await getTokenBalance(pool, token1);

  // Get token prices from Coingecko
  const [price0, price1] = await getTokenPrices(token0, token1);

  // Calculate TVL
  const tvl = (token0Balance * price0) + (token1Balance * price1);

  // Get 24h volume & fees
  const volume24h = await get24hVolume(poolAddress);
  const fees24h = volume24h * feePercentage;

  // Calculate APY
  const apy = (fees24h * 365 / tvl) * 100;
  return apy;
}
```

**4. Add More Chains**
```javascript
// Collect data from:
// - Polygon (MATIC pools)
// - Arbitrum (L2 pools)
// - Optimism
// - Base

// Just change provider in historical_collector_v2.mjs:
const provider = new ethers.JsonRpcProvider(
  `https://polygon-mainnet.g.alchemy.com/v2/${ALCHEMY_API_KEY}`
);
```

### For Nolan (Model Training)

**1. Try Different Models**
```python
# Instead of RandomForest, try:

# XGBoost (usually best)
from xgboost import XGBRegressor
model = XGBRegressor(n_estimators=100)

# LightGBM (faster)
from lightgbm import LGBMRegressor
model = LGBMRegressor()

# Neural Network
from sklearn.neural_network import MLPRegressor
model = MLPRegressor(hidden_layers=(100, 50))
```

**2. Hyperparameter Tuning**
```python
from sklearn.model_selection import GridSearchCV

param_grid = {
    'n_estimators': [50, 100, 200],
    'max_depth': [5, 10, 15],
    'min_samples_split': [2, 5, 10]
}

grid = GridSearchCV(RandomForestRegressor(), param_grid, cv=5)
grid.fit(X_train, y_train)
best_model = grid.best_estimator_
```

**3. Feature Engineering**
```python
# Add polynomial features
from sklearn.preprocessing import PolynomialFeatures
poly = PolynomialFeatures(degree=2)
X_poly = poly.fit_transform(X)

# Add feature interactions
df['tx_times_fee'] = df['tx_count'] * df['fee_percentage']
df['growth_times_volatility'] = df['tx_growth_rate'] * df['tx_count_7d_std']
```

**4. Pool-Specific Models**
```python
# Train separate models for each pool type
eth_model = train_model(df[df['poolType'] == 'eth_paired'])
stable_model = train_model(df[df['poolType'] == 'stablecoin'])
other_model = train_model(df[df['poolType'] == 'other'])

# Predict based on pool type
if pool_type == 'eth_paired':
    prediction = eth_model.predict(features)
elif pool_type == 'stablecoin':
    prediction = stable_model.predict(features)
else:
    prediction = other_model.predict(features)
```

---

## 💡 IMPORTANT NOTES FOR TOMORROW

### What This Project Does
**In simple terms:**
1. Collects 30 days of swap transactions from Ethereum
2. Organizes them by pool and date
3. Calculates features (transaction counts, trends, etc.)
4. Creates targets (future transaction counts)
5. Gives Nolan clean CSV files to train a model

**Goal:** Predict which pools will be most active in the future (as proxy for best APY/returns)

### Key Files to Remember
```
⭐⭐⭐ GIVE TO NOLAN:
1. pool_training_data.csv
2. pool_test_data.csv
3. DATA_FOR_NOLAN.md

📖 FOR YOUR REFERENCE:
- TECHNICAL_DOCUMENTATION.md (this file)
- PROJECT_COMPLETE_SUMMARY.md

🔧 TO RUN PIPELINE AGAIN:
- updater/historical_collector_v2.mjs (Phase 1)
- updater/pool_classifier.mjs (Phase 2)
- generate_timeseries_features.py (Phase 3)
- create_training_dataset.py (Phase 4)
```

### Quick Refresh Commands
```bash
# See collected data stats
wc -l updater/static/pool_logs_30d_*.csv

# See classified pools
wc -l updater/static/pool_metadata.csv

# See training data
wc -l pool_training_data.csv
head pool_training_data.csv

# Re-run any phase (see "How to Run Entire Pipeline" section above)
```

### If Something Breaks
1. **Check ALCHEMY_API_KEY:** `cat .env` and `cat updater/.env`
2. **Check dependencies:** `npm list` and `pip list`
3. **Check Python environment:** `source updater/venv/bin/activate`
4. **See error logs:** Check terminal output for specific errors
5. **Refer to:** Troubleshooting section in this doc

### Expected Model Performance (For Nolan)
```
Baseline (RandomForest):
  - R² Score: 0.70-0.80
  - MAE: 50-100 transactions

Good Model:
  - R² Score: > 0.75
  - MAE: < 75 transactions

Excellent Model:
  - R² Score: > 0.85
  - MAE: < 50 transactions
```

---

## 📞 QUESTIONS YOU MIGHT HAVE TOMORROW

### Q: Where did the 30 days come from?
**A:** Ethereum blocks. We calculated:
- Current block: 23,708,339
- 30 days ago: 23,708,339 - (7,200 blocks/day × 30 days) = 23,492,339
- Fetched all swap events between these blocks

### Q: Why transaction count instead of APY?
**A:** Easier to predict, strongly correlated with APY (more txs = more fees = higher APY), and we already have the data.

### Q: Can we collect more than 30 days?
**A:** Yes! Just run:
```bash
cd updater
node historical_collector_v2.mjs 60  # For 60 days
```

### Q: How do I update this with new data daily?
**A:** Create a script that:
1. Fetches last 24 hours
2. Appends to existing CSV
3. Re-runs Phase 3 & 4 to regenerate features
4. Nolan retrains model weekly

### Q: What if Nolan gets bad accuracy?
**A:** Could be:
1. **Not enough data:** Collect more days (60-90)
2. **Need better features:** Add prices, TVL, gas costs
3. **Wrong model:** Try XGBoost instead of RandomForest
4. **Pool-specific behavior:** Train separate models per pool type

### Q: Where's the Alchemy API key stored?
**A:** In `.env` and `updater/.env` - **keep it secret!**

### Q: Can this work for predicting actual trading/investment?
**A:** Yes, but you'd need:
1. Real-time data pipeline (not just historical)
2. Actual APY calculations (not just transaction proxy)
3. Risk management (don't trust predictions blindly)
4. Regular model retraining (market changes)

---

## 🎯 SUCCESS METRICS

### Pipeline Success (Your Work)
- [x] Collected 30 days of data ✅
- [x] Classified all pools ✅
- [x] Generated time-series features ✅
- [x] Created clean training datasets ✅
- [x] Documented everything ✅

### Model Success (Nolan's Work)
- [ ] Train baseline model (RandomForest)
- [ ] Achieve R² > 0.70
- [ ] Test on validation set
- [ ] Identify top-performing pools
- [ ] Beat naive baseline (predicting mean)

### Business Success (If Deploying)
- [ ] Model accuracy consistently > 75%
- [ ] Predictions update daily
- [ ] API serves predictions in < 1 second
- [ ] Track actual vs predicted performance
- [ ] Make profitable pool recommendations

---

## 📚 ADDITIONAL RESOURCES

### Learn More About:

**Time-Series Prediction:**
- Rolling windows and moving averages
- Temporal train/test splits
- Autocorrelation and stationarity

**Pool Mechanics:**
- Uniswap V3 concentrated liquidity
- Impermanent loss
- Fee tiers and their impact

**Model Evaluation:**
- R² score (coefficient of determination)
- MAE (Mean Absolute Error)
- RMSE (Root Mean Squared Error)
- Walk-forward validation

### Useful Links:
- Uniswap V3 Docs: https://docs.uniswap.org/contracts/v3/overview
- Alchemy API Docs: https://docs.alchemy.com/reference/api-overview
- Pandas Time Series: https://pandas.pydata.org/docs/user_guide/timeseries.html
- Scikit-learn: https://scikit-learn.org/stable/

---

**END OF TECHNICAL DOCUMENTATION**

_Last Updated: November 2, 2025_
_Total Time Invested: ~48 minutes (pipeline execution)_
_Status: ✅ COMPLETE - Ready for Nolan_
