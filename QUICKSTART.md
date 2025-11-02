# 🚀 Quick Start - ETH Pool APY Prediction

## ⚡ TL;DR - Get Data Now!

```bash
# 1. Install dependencies (one-time setup)
pip install pandas boto3 networkx scikit-learn web3

# 2. Run the test pipeline
python test_pipeline.py

# 3. View your data
open eth_pool_features_test.csv
```

That's it! You now have APY predictions for ETH pools.

---

## 🎯 What You Just Built

Your Alchemy API key is configured and integrated into:

### 1. **Data Collection** (`updater/oneinch_swaps.cjs`)
- Fetches swap transactions from Ethereum
- Uses: `provider.getLogs()` to get swap events
- Already working!

### 2. **Pool State Fetcher** (`updater/pool_state_fetcher.mjs`)
- Queries pool reserves, TVL, fee tiers
- Uses: `pool.token0()`, `pool.liquidity()`, `slot0()`
- Gets token metadata: symbol, decimals

### 3. **APY Feature Engine** (`apy_features.py`)
- Calculates 15+ features per pool
- Filters for ETH pools only
- Estimates APY based on volume and fees

### 4. **Data Viewer** (`view_pool_data.py`)
- Interactive data exploration
- Filter, analyze, export
- Generate features on-demand

---

## 📊 See Your Data

### Method 1: Excel (Easiest)
```bash
open eth_pool_features_test.csv
```

You'll see columns like:
- `contract` - Pool address
- `paired_token` - Token paired with ETH (USDC, DAI, etc.)
- `current_tvl_usd` - Total Value Locked in USD
- `estimated_current_apy` - Predicted APY %
- `tx_count` - Number of transactions
- `fee_percentage` - Pool fee (0.003 = 0.3%)

### Method 2: Python
```python
import pandas as pd

df = pd.read_csv('eth_pool_features_test.csv')

# Top 10 by APY
print(df.nlargest(10, 'estimated_current_apy')[
    ['paired_token', 'current_tvl_usd', 'estimated_current_apy']
])

# High TVL pools
high_tvl = df[df['current_tvl_usd'] > 1_000_000]
print(f"Pools with >$1M TVL: {len(high_tvl)}")
```

### Method 3: Command Line
```bash
# View summary
python view_pool_data.py --source local --key updater/static/test_logs.csv

# ETH pools only
python view_pool_data.py --source local --key updater/static/test_logs.csv --eth-only

# Generate fresh features
python view_pool_data.py --source local --key updater/static/test_logs.csv --generate-features --max-pools 20
```

---

## 🔑 How Alchemy is Used

Your API key (`xZAA_UQS9ExBekaML58M0-T5BNvKZeRI`) is used for:

### 1. Getting Current Block Number
```javascript
const currentBlock = await provider.getBlockNumber();
```

### 2. Fetching Swap Events
```javascript
const logs = await provider.getLogs({
  fromBlock,
  toBlock,
  address: poolAddresses
});
```

### 3. Querying Pool State
```python
pool = w3.eth.contract(address=pool_address, abi=POOL_ABI)
reserve0 = pool.functions.token0().call()
fee_tier = pool.functions.fee().call()
```

### 4. Getting Token Info
```python
token = w3.eth.contract(address=token_address, abi=ERC20_ABI)
symbol = token.functions.symbol().call()  # "USDC", "DAI", etc.
decimals = token.functions.decimals().call()
```

### 5. Calculating Reserves
```python
token_contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)
balance = token_contract.functions.balanceOf(pool_address).call()
```

---

## 🗄️ Database Setup (5 minutes)

### SQLite (Simplest)
```python
import sqlite3
import pandas as pd

# Create database
conn = sqlite3.connect('eth_pools.db')

# Load your data
df = pd.read_csv('eth_pool_features_test.csv')
df.to_sql('pools', conn, if_exists='replace', index=False)

# Query
query = "SELECT * FROM pools WHERE estimated_current_apy > 10"
results = pd.read_sql_query(query, conn)
print(results)

# Close
conn.close()
```

Now you can query with SQL:
```sql
SELECT paired_token, AVG(estimated_current_apy) as avg_apy
FROM pools
GROUP BY paired_token
ORDER BY avg_apy DESC;
```

### PostgreSQL (Production)
```bash
# 1. Install PostgreSQL (Mac)
brew install postgresql
brew services start postgresql

# 2. Create database
createdb defi_data

# 3. Load data (Python)
from sqlalchemy import create_engine
engine = create_engine('postgresql://localhost/defi_data')
df.to_sql('eth_pools', engine, if_exists='replace')
```

---

## 🔄 Collect Fresh Data Anytime

```bash
# Collect latest 1000 blocks
python test_pipeline.py

# Or use the data viewer
python view_pool_data.py --source local --key updater/static/test_logs.csv --generate-features
```

---

## 📁 Files Created

```
✅ .env                          # Alchemy API key
✅ updater/.env                  # Alchemy API key (copy)
✅ updater/pool_state_fetcher.mjs # Pool state queries
✅ apy_features.py               # APY calculation engine
✅ view_pool_data.py             # Data viewer
✅ test_pipeline.py              # Quick test script
✅ README_APY_MODEL.md           # Full documentation
```

---

## ⚠️ Common Issues

### "No data collected"
- Check internet connection
- Verify Alchemy API key is valid
- Try reducing block range in `oneinch_swaps.cjs`

### "No ETH pools found"
- You might be querying a period with low ETH activity
- Try increasing `max_pools` parameter
- Check that WETH address is correct

### Rate limiting
- Add delays: `time.sleep(0.2)` between pool queries
- Reduce `max_pools` to 5-10 for testing

---

## 🎯 Next Steps

1. ✅ **Explore the data** - Open CSV in Excel
2. ✅ **Set up a database** - SQLite is easiest
3. ⏭️ **Update ML model** - Change from classification to regression
4. ⏭️ **Automate collection** - Set up daily cron job
5. ⏭️ **Build API** - Serve predictions via REST API

---

## 🆘 Quick Commands

```bash
# See all options for data viewer
python view_pool_data.py --help

# Test Alchemy connection
python -c "from apy_features import w3; print('Connected:', w3.is_connected())"

# Check dependencies
pip list | grep -E 'pandas|boto3|web3|sklearn'

# View sample data
python -c "import pandas as pd; df=pd.read_csv('eth_pool_features_test.csv'); print(df.head())"
```

Ready to predict some APYs! 🚀
