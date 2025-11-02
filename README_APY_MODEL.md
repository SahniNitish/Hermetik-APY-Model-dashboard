# ETH Pool APY Prediction Model

Transform your DeFi liquidity model into an **APY prediction system** for Ethereum pools.

## 🎯 What This Does

Predicts the **Annual Percentage Yield (APY)** for ETH liquidity pools by:
- Collecting real-time swap transaction data from Ethereum
- Analyzing pool states (TVL, reserves, fees) via Alchemy API
- Calculating network centrality metrics
- Training ML models to predict future APY

---

## 📁 Project Structure

```
caduceus-model/
├── updater/                          # Node.js data collection
│   ├── oneinch_swaps.cjs            # Fetch swap transactions
│   ├── pool_state_fetcher.mjs       # Query pool states (NEW)
│   ├── update_token_graphs.mjs      # Orchestrate updates
│   └── .env                         # API keys
│
├── apy_features.py                   # APY feature engineering (NEW)
├── view_pool_data.py                 # Data viewer/analyzer (NEW)
├── test_pipeline.py                  # Quick test script (NEW)
├── main_ec2.py                       # ML training (to be updated)
└── .env                              # Environment variables
```

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Node.js dependencies
cd updater
npm install

# Python dependencies
cd ..
pip install pandas boto3 networkx scikit-learn web3
```

### 2. Set Up Alchemy API Key

Already configured! Your key is in `.env`:
```
ALCHEMY_API_KEY=xZAA_UQS9ExBekaML58M0-T5BNvKZeRI
```

### 3. Run the Test Pipeline

```bash
python test_pipeline.py
```

This will:
1. ✅ Collect recent swap data from Ethereum (last ~1000 blocks)
2. ✅ Analyze transactions to find ETH pools
3. ✅ Generate APY prediction features using Alchemy
4. ✅ Save results to `eth_pool_features_test.csv`

---

## 📊 View Your Data

### Option 1: Excel/Google Sheets (Easiest)
```bash
# Open the generated CSV
open eth_pool_features_test.csv
```

### Option 2: Command Line Viewer
```bash
# View summary of collected data
python view_pool_data.py --source local --key updater/static/test_logs.csv

# Filter for ETH pools only
python view_pool_data.py --source local --key updater/static/test_logs.csv --eth-only

# Generate live features
python view_pool_data.py --source local --key updater/static/test_logs.csv --generate-features
```

### Option 3: Python Script
```python
import pandas as pd

# Load features
df = pd.read_csv('eth_pool_features_test.csv')

# View top APY pools
top_apy = df.nlargest(10, 'estimated_current_apy')
print(top_apy[['paired_token', 'current_tvl_usd', 'estimated_current_apy']])

# Filter by TVL
high_tvl = df[df['current_tvl_usd'] > 1000000]
print(f"Pools with >$1M TVL: {len(high_tvl)}")
```

---

## 🔬 Features Generated

For each ETH pool, the system calculates:

### Financial Metrics
- `current_tvl_eth` - Total Value Locked in ETH
- `current_tvl_usd` - Total Value Locked in USD
- `eth_reserve` - Amount of ETH in pool
- `fee_tier` - Pool fee tier (e.g., 3000 = 0.3%)
- `fee_percentage` - Fee as decimal (e.g., 0.003)

### Volume & Activity
- `tx_count` - Number of transactions
- `unique_users` - Unique wallet addresses
- `activity_span` - Block range of activity
- `avg_tx_per_block` - Transaction density

### Revenue Estimates
- `estimated_volume_usd` - Estimated trading volume
- `estimated_fee_revenue` - Estimated fees collected
- `avg_swap_size_usd` - Average swap size

### APY Prediction
- `estimated_current_apy` - Estimated current APY %
- `paired_token` - Token paired with ETH (USDC, DAI, etc.)

### Network Centrality (from existing model)
- `betweenness_centrality` - Bridge importance
- `closeness_centrality` - Network accessibility
- `eigenvector_centrality` - Connection quality

---

## 🗄️ Database Integration

### SQLite (Local)
```python
import sqlite3
import pandas as pd

# Create database
conn = sqlite3.connect('eth_pools.db')

# Load CSV to database
df = pd.read_csv('eth_pool_features_test.csv')
df.to_sql('pools', conn, if_exists='replace', index=False)

# Query
query = "SELECT * FROM pools WHERE estimated_current_apy > 10 ORDER BY current_tvl_usd DESC"
results = pd.read_sql_query(query, conn)
print(results)
```

### PostgreSQL (Production)
```python
from sqlalchemy import create_engine
import pandas as pd

# Connect
engine = create_engine('postgresql://user:pass@localhost:5432/defi')

# Load data
df = pd.read_csv('eth_pool_features_test.csv')
df.to_sql('eth_pools', engine, if_exists='replace', index=False)

# Query
query = """
    SELECT paired_token,
           AVG(estimated_current_apy) as avg_apy,
           SUM(current_tvl_usd) as total_tvl
    FROM eth_pools
    GROUP BY paired_token
    ORDER BY avg_apy DESC
"""
results = pd.read_sql_query(query, engine)
```

### MongoDB (NoSQL)
```python
from pymongo import MongoClient
import pandas as pd

# Connect
client = MongoClient('mongodb://localhost:27017/')
db = client['defi_database']
collection = db['eth_pools']

# Insert data
df = pd.read_csv('eth_pool_features_test.csv')
collection.insert_many(df.to_dict('records'))

# Query
high_apy = list(collection.find(
    {"estimated_current_apy": {"$gt": 10}},
    {"paired_token": 1, "estimated_current_apy": 1, "current_tvl_usd": 1}
).sort("current_tvl_usd", -1))
```

---

## 🔄 Automated Data Collection

### Daily Updates
```bash
# Collect latest data and upload to S3
python s3_updater.py --bucket defi-liquidity-data
```

### Schedule with Cron
```bash
# Edit crontab
crontab -e

# Add this line to run daily at 2 AM
0 2 * * * cd /path/to/caduceus-model && python s3_updater.py --bucket defi-liquidity-data
```

---

## 🤖 Machine Learning Pipeline

### 1. Generate Training Dataset
```bash
python main_ec2.py --bucket defi-liquidity-data generate-from-rolling --lookback 1W
```

### 2. Train APY Regression Model
```bash
# TODO: Update main_ec2.py to use regression instead of classification
# For now, this trains the old classification model
python main_ec2.py --bucket defi-liquidity-data train-model --lookback 1w
```

### 3. Get Predictions
```bash
python main_ec2.py --bucket defi-liquidity-data infer-multi --top 20 --timeframes 1D 3D 1W
```

---

## 🔑 How Alchemy API is Used

### 1. **Pool State Queries** (`pool_state_fetcher.mjs`)
```javascript
// Get pool reserves, prices, fee tiers
const poolState = await fetchUniV3PoolState(poolAddress);
```

### 2. **Token Metadata** (`apy_features.py`)
```python
# Get token symbols, decimals
token_contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)
symbol = token_contract.functions.symbol().call()
```

### 3. **Real-time Data** (`oneinch_swaps.cjs`)
```javascript
// Fetch recent swap events
const logs = await provider.getLogs({
  fromBlock, toBlock,
  address: poolAddresses
});
```

### 4. **Historical State** (future enhancement)
```python
# Query pool state at specific block
pool_state = pool.functions.liquidity().call(block_identifier=block_number)
```

---

## 📈 Next Steps

### Phase 1: Data Collection (DONE ✅)
- [x] Set up Alchemy API integration
- [x] Create pool state fetcher
- [x] Add ETH pool filtering
- [x] Generate features

### Phase 2: Model Updates (TODO)
- [ ] Update `main_ec2.py` to use regression instead of classification
- [ ] Change target from binary label to continuous APY
- [ ] Add new features to model training
- [ ] Implement APY calculation for historical labels

### Phase 3: Production (TODO)
- [ ] Set up automated daily data collection
- [ ] Deploy to EC2/Cloud
- [ ] Create API endpoint for predictions
- [ ] Build monitoring dashboard

---

## 🐛 Troubleshooting

### "ALCHEMY_API_KEY not found"
- Make sure `.env` file exists in both root and `updater/` directories
- Check that the key is correctly set: `xZAA_UQS9ExBekaML58M0-T5BNvKZeRI`

### "No ETH pools found"
- Ensure your data has recent transactions (last ~7200 blocks)
- Check that WETH address is correct: `0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2`

### "Rate limiting" errors
- Add delays between API calls: `time.sleep(0.2)`
- Reduce `max_pools` parameter when generating features

### Dependencies missing
```bash
# Node.js
cd updater && npm install

# Python
pip install pandas boto3 networkx scikit-learn web3
```

---

## 📞 Support

For issues or questions:
1. Check the generated CSV files to see what data was collected
2. Run `python test_pipeline.py` to test the full pipeline
3. Use `python view_pool_data.py --help` to see all options

---

## 🎯 Example Output

```
📊 ETH Pool Features Summary:

contract                                      paired_token  current_tvl_usd  tx_count  estimated_current_apy
0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640   USDC          $45,234,567      1,234     12.5%
0xCBCdF9626bC03E24f779434178A73a0B4bad62eD   WBTC          $23,456,789      567       8.3%
0x4e68Ccd3E89f51C3074ca5072bbAC773960dFa36   USDT          $18,765,432      892       15.2%
```

Happy APY predicting! 🚀
