# 🗄️ Database Guide - ETH Pool APY Prediction

## ✅ Database is Connected!

Your data is now in **SQLite database**: `eth_pools.db`

### 📊 Current Database Stats:
- **Total Pools**: 5 ETH pools
- **Total TVL**: $81.25 million
- **Average APY**: 80.8%
- **Total Transactions**: 1,456

---

## 🚀 Quick Start - 3 Ways to Query

### **Option 1: Easy Query Script (Recommended)**

```bash
source updater/venv/bin/activate

# Show all pools
python3 query_db.py all

# Top 3 pools by APY
python3 query_db.py top 3

# Pools with TVL > $10M
python3 query_db.py tvl 10000000

# USDC pools only
python3 query_db.py token USDC

# Statistics
python3 query_db.py stats

# Custom SQL
python3 query_db.py query "SELECT * FROM pools WHERE estimated_current_apy > 50"
```

### **Option 2: Direct SQLite Commands**

```bash
# Open database
sqlite3 eth_pools.db

# List tables
.tables

# Show schema
.schema pools

# Query
SELECT paired_token, estimated_current_apy FROM pools ORDER BY estimated_current_apy DESC;

# Formatted output
.mode column
.headers on
SELECT * FROM pools;

# Exit
.quit
```

### **Option 3: Python Code**

```python
import sqlite3
import pandas as pd

# Connect
conn = sqlite3.connect('eth_pools.db')

# Query with pandas
df = pd.read_sql_query("SELECT * FROM pools", conn)
print(df)

# Query specific
query = """
SELECT paired_token, estimated_current_apy
FROM pools
WHERE estimated_current_apy > 20
ORDER BY estimated_current_apy DESC
"""
results = pd.read_sql_query(query, conn)
print(results)

# Close
conn.close()
```

---

## 📋 Database Schema

**Table**: `pools`

| Column | Type | Description |
|--------|------|-------------|
| `contract` | TEXT | Pool contract address |
| `timestamp` | TEXT | When features were calculated |
| `current_tvl_eth` | REAL | TVL in ETH |
| `current_tvl_usd` | REAL | TVL in USD |
| `eth_reserve` | REAL | ETH reserve in pool |
| `fee_tier` | INTEGER | Fee tier (500 = 0.05%) |
| `fee_percentage` | REAL | Fee as decimal (0.0005) |
| `tx_count` | INTEGER | Transaction count |
| `unique_users` | INTEGER | Unique wallet addresses |
| `activity_span` | INTEGER | Block range |
| `avg_tx_per_block` | REAL | Transaction density |
| `estimated_volume_usd` | REAL | Estimated volume |
| `estimated_fee_revenue` | REAL | Estimated fees |
| `avg_swap_size_usd` | REAL | Average swap size |
| `paired_token` | TEXT | Token symbol (USDC, USDT, etc.) |
| `paired_token_address` | TEXT | Token contract address |
| **`estimated_current_apy`** | REAL | **Predicted APY %** |

---

## 🔍 Example SQL Queries

### **1. Top Pools by APY**
```sql
SELECT
    paired_token,
    ROUND(current_tvl_usd/1000000, 2) as tvl_millions,
    tx_count,
    ROUND(estimated_current_apy, 2) as apy_percent
FROM pools
ORDER BY estimated_current_apy DESC
LIMIT 5;
```

### **2. High TVL Pools**
```sql
SELECT
    contract,
    paired_token,
    ROUND(current_tvl_usd, 2) as tvl_usd,
    ROUND(estimated_current_apy, 2) as apy_percent
FROM pools
WHERE current_tvl_usd > 10000000
ORDER BY current_tvl_usd DESC;
```

### **3. Average APY by Token**
```sql
SELECT
    paired_token,
    COUNT(*) as pool_count,
    ROUND(AVG(current_tvl_usd)/1000000, 2) as avg_tvl_millions,
    ROUND(AVG(estimated_current_apy), 2) as avg_apy
FROM pools
GROUP BY paired_token
ORDER BY avg_apy DESC;
```

### **4. Best Pools (High APY + Good TVL)**
```sql
SELECT
    paired_token,
    ROUND(current_tvl_usd/1000000, 2) as tvl_millions,
    tx_count,
    ROUND(estimated_current_apy, 2) as apy_percent,
    ROUND(fee_percentage * 100, 3) as fee_percent
FROM pools
WHERE estimated_current_apy > 20
  AND current_tvl_usd > 1000000
ORDER BY estimated_current_apy DESC;
```

### **5. Active Pools (High Transaction Volume)**
```sql
SELECT
    paired_token,
    tx_count,
    unique_users,
    ROUND(estimated_current_apy, 2) as apy_percent
FROM pools
WHERE tx_count > 100
ORDER BY tx_count DESC;
```

### **6. Search by Token**
```sql
SELECT * FROM pools
WHERE paired_token = 'USDC'
ORDER BY estimated_current_apy DESC;
```

---

## 📊 Python Analysis Examples

### **Load and Analyze**
```python
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt

# Connect
conn = sqlite3.connect('eth_pools.db')
df = pd.read_sql_query("SELECT * FROM pools", conn)
conn.close()

# 1. Summary statistics
print(df.describe())

# 2. Top 3 by APY
top3 = df.nlargest(3, 'estimated_current_apy')
print(top3[['paired_token', 'estimated_current_apy']])

# 3. Plot APY distribution
df.plot(x='paired_token', y='estimated_current_apy', kind='bar')
plt.title('APY by Pool')
plt.ylabel('APY %')
plt.show()

# 4. TVL vs APY scatter plot
plt.scatter(df['current_tvl_usd'], df['estimated_current_apy'])
plt.xlabel('TVL (USD)')
plt.ylabel('APY %')
plt.title('TVL vs APY')
plt.show()
```

### **Filter and Export**
```python
import sqlite3
import pandas as pd

conn = sqlite3.connect('eth_pools.db')

# Get high APY pools
high_apy = pd.read_sql_query("""
    SELECT * FROM pools
    WHERE estimated_current_apy > 20
    ORDER BY estimated_current_apy DESC
""", conn)

# Export to CSV
high_apy.to_csv('high_apy_pools.csv', index=False)
print(f"Exported {len(high_apy)} high APY pools")

conn.close()
```

---

## 🔄 Update Database with New Data

### **Manual Update**
```bash
# 1. Collect fresh data
python3 test_pipeline.py

# 2. Update database
python3 << 'EOF'
import sqlite3
import pandas as pd

df = pd.read_csv('eth_pool_features_test.csv')
conn = sqlite3.connect('eth_pools.db')
df.to_sql('pools', conn, if_exists='replace', index=False)
print(f"✅ Updated database with {len(df)} pools")
conn.close()
EOF
```

### **Automated Update Script**
```bash
#!/bin/bash
# save as update_db.sh

source updater/venv/bin/activate
export ALCHEMY_API_KEY=xZAA_UQS9ExBekaML58M0-T5BNvKZeRI

# Collect data
python3 test_pipeline.py

# Update database
python3 -c "
import sqlite3, pandas as pd
df = pd.read_csv('eth_pool_features_test.csv')
conn = sqlite3.connect('eth_pools.db')
df.to_sql('pools', conn, if_exists='replace', index=False)
conn.close()
print('Database updated!')
"
```

---

## 🌐 PostgreSQL Setup (Production)

### **Install PostgreSQL**
```bash
# Mac
brew install postgresql
brew services start postgresql

# Ubuntu
sudo apt-get install postgresql postgresql-contrib
sudo service postgresql start
```

### **Create Database**
```bash
psql postgres
CREATE DATABASE defi_pools;
\q
```

### **Load Data**
```python
from sqlalchemy import create_engine
import pandas as pd

# Connect
engine = create_engine('postgresql://localhost/defi_pools')

# Load data
df = pd.read_csv('eth_pool_features_test.csv')
df.to_sql('pools', engine, if_exists='replace', index=False)

# Query
query = "SELECT * FROM pools WHERE estimated_current_apy > 20"
results = pd.read_sql_query(query, engine)
print(results)
```

### **Query PostgreSQL**
```bash
psql defi_pools

SELECT paired_token, estimated_current_apy
FROM pools
ORDER BY estimated_current_apy DESC;
```

---

## 🍃 MongoDB Setup (NoSQL)

### **Install MongoDB**
```bash
# Mac
brew tap mongodb/brew
brew install mongodb-community
brew services start mongodb-community

# Ubuntu
sudo apt-get install mongodb
```

### **Load Data**
```python
from pymongo import MongoClient
import pandas as pd

# Connect
client = MongoClient('mongodb://localhost:27017/')
db = client['defi_database']
collection = db['eth_pools']

# Load data
df = pd.read_csv('eth_pool_features_test.csv')
records = df.to_dict('records')
collection.insert_many(records)

# Query
high_apy = list(collection.find(
    {"estimated_current_apy": {"$gt": 20}},
    {"paired_token": 1, "estimated_current_apy": 1, "_id": 0}
).sort("estimated_current_apy", -1))

for pool in high_apy:
    print(f"{pool['paired_token']}: {pool['estimated_current_apy']:.2f}%")
```

---

## 📈 Current Database Contents

Run this to see what's in your database:

```bash
python3 query_db.py all
```

**Current Results:**

| Token | TVL | APY | Transactions |
|-------|-----|-----|--------------|
| wTAO/ETH | $946K | **317.55%** 🔥 | 87 |
| USDT/ETH | $9.9M | **24.71%** | 677 |
| USDC/ETH | $27.2M | **24.27%** | 133 |
| WBTC/ETH | $38.3M | **21.35%** | 117 |
| USDC/ETH | $4.9M | **16.13%** | 442 |

---

## 🆘 Troubleshooting

### Database not found
```bash
# Recreate database
python3 test_pipeline.py
```

### Permission errors
```bash
chmod 644 eth_pools.db
```

### Query errors
```bash
# Check table exists
sqlite3 eth_pools.db ".tables"

# Check schema
sqlite3 eth_pools.db ".schema pools"
```

---

## 🎯 Next Steps

1. ✅ **Query your data** - Use `python3 query_db.py`
2. ✅ **Export results** - Run queries and save to CSV
3. ⏭️ **Set up PostgreSQL** - For production use
4. ⏭️ **Create visualizations** - Use matplotlib/plotly
5. ⏭️ **Build API** - Serve data via REST API

---

**Your database is ready to use!** 🎉

Use `python3 query_db.py` for easy queries, or connect directly with SQLite/Python.
