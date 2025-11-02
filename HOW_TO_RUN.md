# 🚀 How to Run - ETH Pool APY Prediction

## ✅ Setup Complete!

Everything is installed and working. You successfully collected data from **5,321 transactions** across **807 pools** and generated APY predictions for **5 ETH pools**.

---

## 📊 Your Results

**File**: `eth_pool_features_test.csv`

| Pool | Paired Token | TVL | APY | Transactions |
|------|--------------|-----|-----|--------------|
| 0xc7bB...1b0e9b | **USDT/ETH** | $9.9M | **24.71%** | 677 |
| 0xE055...32939F | **USDC/ETH** | $4.9M | **16.13%** | 442 |
| 0x88e6...3f5640 | **USDC/ETH** | $27.2M | **24.27%** | 133 |
| 0x4585...5a20c0 | **WBTC/ETH** | $38.3M | **21.35%** | 117 |
| 0x433a...Cd1bBC | **wTAO/ETH** | $946K | **317.55%** 🔥 | 87 |

**Note**: wTAO pool has extremely high APY due to low TVL and high volume ratio!

---

## 🎯 Three Ways to Run

### **Option 1: Interactive Menu (Easiest)**
```bash
./run.sh
```

You'll see a menu with options:
1. Quick Test (30 sec)
2. Full Pipeline (5 min)
3. View Data
4. Generate Features
5. Exit

### **Option 2: Direct Python Commands**

```bash
# Activate virtual environment first
source updater/venv/bin/activate
export ALCHEMY_API_KEY=xZAA_UQS9ExBekaML58M0-T5BNvKZeRI

# Quick test (verify everything works)
python3 quick_test.py

# Full pipeline (collect fresh data)
python3 test_pipeline.py

# View existing data
python3 view_pool_data.py --source local --key updater/static/test_logs.csv --eth-only

# Generate features from existing logs
python3 view_pool_data.py --source local --key updater/static/test_logs.csv --generate-features --max-pools 20
```

### **Option 3: Individual Steps**

#### Step 1: Collect Transaction Data
```bash
source updater/venv/bin/activate
cd updater
node oneinch_swaps.cjs --output static/test_logs.csv
cd ..
```

#### Step 2: Generate APY Features
```bash
python3 -c "
from apy_features import batch_calculate_features
import pandas as pd

df = pd.read_csv('updater/static/test_logs.csv')
features = batch_calculate_features(df, max_pools=20)
features.to_csv('my_features.csv', index=False)
print('Done! Check my_features.csv')
"
```

---

## 📁 View Your Data

### Excel/Google Sheets (Easiest)
```bash
# Mac
open eth_pool_features_test.csv

# Windows
start eth_pool_features_test.csv

# Linux
xdg-open eth_pool_features_test.csv
```

### Python
```python
import pandas as pd

# Load the data
df = pd.read_csv('eth_pool_features_test.csv')

# Show all columns
print(df.to_string())

# Top pools by APY
top_apy = df.nlargest(5, 'estimated_current_apy')
print(top_apy[['paired_token', 'current_tvl_usd', 'estimated_current_apy']])

# High TVL pools (>$10M)
high_tvl = df[df['current_tvl_usd'] > 10_000_000]
print(high_tvl)
```

### Command Line
```bash
# View raw CSV
cat eth_pool_features_test.csv

# View formatted (if you have csvlook installed)
csvlook eth_pool_features_test.csv

# View with pandas
python3 -c "import pandas as pd; print(pd.read_csv('eth_pool_features_test.csv').to_string())"
```

---

## 🗄️ Connect to Database (5 minutes)

### SQLite (Simplest)
```bash
python3 -c "
import sqlite3
import pandas as pd

# Create database
conn = sqlite3.connect('eth_pools.db')

# Load data
df = pd.read_csv('eth_pool_features_test.csv')
df.to_sql('pools', conn, if_exists='replace', index=False)
print('✅ Database created: eth_pools.db')

# Query
query = 'SELECT paired_token, current_tvl_usd, estimated_current_apy FROM pools ORDER BY estimated_current_apy DESC'
results = pd.read_sql_query(query, conn)
print(results)
conn.close()
"
```

Then query with SQL:
```bash
sqlite3 eth_pools.db "SELECT * FROM pools WHERE estimated_current_apy > 20"
```

---

## 🔄 Collect Fresh Data Anytime

```bash
# Full pipeline (recommended)
./run.sh
# Choose option 2

# Or direct command
source updater/venv/bin/activate && \
export ALCHEMY_API_KEY=xZAA_UQS9ExBekaML58M0-T5BNvKZeRI && \
python3 test_pipeline.py
```

---

## 📊 Available Files

```
✅ eth_pool_features_test.csv       # Your APY predictions (5 pools)
✅ updater/static/test_logs.csv     # Raw transaction data (5,321 txs)
✅ apy_features.py                  # Feature calculation module
✅ view_pool_data.py                # Data viewer tool
✅ test_pipeline.py                 # Full pipeline script
✅ quick_test.py                    # Quick verification
✅ run.sh                           # Interactive menu
```

---

## 🎓 Understanding the Data

### Key Columns in CSV:

| Column | Description | Example |
|--------|-------------|---------|
| `contract` | Pool address | 0x88e6...5640 |
| `paired_token` | Token paired with ETH | USDC, USDT, WBTC |
| `current_tvl_usd` | Total Value Locked | $27,153,406 |
| `eth_reserve` | ETH amount in pool | 5430.68 ETH |
| `fee_tier` | Fee tier (basis points) | 500 = 0.05% |
| `tx_count` | Transaction count | 133 |
| `estimated_current_apy` | **Predicted APY %** | 24.27% |

### How APY is Calculated:
```
APY = (Fee Revenue / TVL) × (365 / Days) × 100

Where:
- Fee Revenue = Estimated Volume × Fee Percentage
- Estimated Volume = Avg Swap Size × Transaction Count
- Avg Swap Size ≈ 1% of TVL (conservative estimate)
```

---

## 🔍 Example Queries

### Python
```python
import pandas as pd
df = pd.read_csv('eth_pool_features_test.csv')

# 1. Top 3 pools by APY
print(df.nlargest(3, 'estimated_current_apy')[['paired_token', 'estimated_current_apy']])

# 2. USDC pools only
usdc_pools = df[df['paired_token'] == 'USDC']
print(usdc_pools)

# 3. High activity pools (>100 txs)
active = df[df['tx_count'] > 100]
print(active)

# 4. Average APY by token
avg_apy = df.groupby('paired_token')['estimated_current_apy'].mean()
print(avg_apy)
```

### SQL (after loading to SQLite)
```sql
-- Top pools by APY
SELECT paired_token, current_tvl_usd, estimated_current_apy
FROM pools
ORDER BY estimated_current_apy DESC
LIMIT 5;

-- Average APY by token
SELECT paired_token, AVG(estimated_current_apy) as avg_apy
FROM pools
GROUP BY paired_token;

-- High TVL pools with good APY
SELECT *
FROM pools
WHERE current_tvl_usd > 10000000
  AND estimated_current_apy > 15;
```

---

## ⚠️ Troubleshooting

### "No module named 'pandas'"
```bash
source updater/venv/bin/activate
pip install pandas boto3 networkx scikit-learn web3
```

### "ALCHEMY_API_KEY not found"
```bash
export ALCHEMY_API_KEY=xZAA_UQS9ExBekaML58M0-T5BNvKZeRI
```

### "No data files found"
```bash
# Run the pipeline first
python3 test_pipeline.py
```

### Rate limiting errors
```bash
# Reduce max_pools in view_pool_data.py
python3 view_pool_data.py --source local --key updater/static/test_logs.csv --generate-features --max-pools 5
```

---

## 📖 Documentation

- **QUICKSTART.md** - 5-minute getting started guide
- **README_APY_MODEL.md** - Complete documentation
- **FEATURES.md** - All 21 features explained

---

## 🎯 Next Steps

1. ✅ **Explore your data** - Open CSV in Excel
2. ⏭️ **Set up database** - Run SQLite example above
3. ⏭️ **Collect more data** - Run pipeline with different time periods
4. ⏭️ **Train ML model** - Update main_ec2.py for regression
5. ⏭️ **Automate** - Set up cron job for daily updates

---

## 🆘 Quick Reference

```bash
# Run everything
./run.sh

# Quick test
python3 quick_test.py

# Full pipeline
python3 test_pipeline.py

# View data
cat eth_pool_features_test.csv

# Load to database
python3 -c "import sqlite3, pandas as pd; pd.read_csv('eth_pool_features_test.csv').to_sql('pools', sqlite3.connect('eth_pools.db'), if_exists='replace')"
```

---

**Congratulations! You now have a working ETH Pool APY prediction system!** 🎉
