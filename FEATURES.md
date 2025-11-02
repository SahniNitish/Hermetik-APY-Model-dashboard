# 📊 Complete Feature List for APY Prediction

## Overview
This document lists all 21 features used to predict ETH pool APY.

---

## 🏦 Pool Financial Features (7 features)

### 1. `current_tvl_eth`
- **Description**: Total Value Locked in ETH
- **Calculation**: 2 × ETH reserve in pool
- **Source**: Alchemy API - `balanceOf()` call
- **Example**: 1234.56 ETH

### 2. `current_tvl_usd`
- **Description**: Total Value Locked in USD
- **Calculation**: `current_tvl_eth × ETH_price_USD`
- **Source**: Calculated from reserves + ETH price oracle
- **Example**: $3,086,400

### 3. `eth_reserve`
- **Description**: Amount of ETH in the pool
- **Calculation**: Direct from token balance
- **Source**: Alchemy - `token.balanceOf(poolAddress)`
- **Example**: 617.28 ETH

### 4. `fee_tier`
- **Description**: Pool fee tier (in hundredths of a bip)
- **Calculation**: From pool contract
- **Source**: Alchemy - `pool.fee()`
- **Values**: 500 (0.05%), 3000 (0.3%), 10000 (1%)

### 5. `fee_percentage`
- **Description**: Fee as decimal percentage
- **Calculation**: `fee_tier / 1,000,000`
- **Example**: 0.003 (0.3%)

### 6. `paired_token`
- **Description**: Token symbol paired with ETH
- **Source**: Alchemy - `token.symbol()`
- **Example**: "USDC", "DAI", "USDT"

### 7. `paired_token_address`
- **Description**: Contract address of paired token
- **Source**: Alchemy - `pool.token0()` or `pool.token1()`
- **Example**: 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48

---

## 📈 Volume & Activity Features (4 features)

### 8. `tx_count`
- **Description**: Number of swap transactions in lookback period
- **Calculation**: Count of swap events
- **Source**: Transaction logs
- **Example**: 1,234 transactions

### 9. `unique_users`
- **Description**: Number of unique wallet addresses
- **Calculation**: Count distinct transaction hashes
- **Source**: Transaction logs
- **Example**: 567 unique users

### 10. `activity_span`
- **Description**: Range of blocks with activity
- **Calculation**: `max_block - min_block`
- **Source**: Transaction logs
- **Example**: 7,200 blocks (≈1 day)

### 11. `avg_tx_per_block`
- **Description**: Transaction density
- **Calculation**: `tx_count / activity_span`
- **Source**: Calculated from above
- **Example**: 0.171 tx/block

---

## 💰 Revenue & APY Features (4 features)

### 12. `estimated_volume_usd`
- **Description**: Estimated trading volume in USD
- **Calculation**: `avg_swap_size × tx_count`
- **Assumptions**: avg_swap_size ≈ 1% of TVL
- **Example**: $4,523,456

### 13. `estimated_fee_revenue`
- **Description**: Estimated fees collected
- **Calculation**: `estimated_volume_usd × fee_percentage`
- **Example**: $13,570 (at 0.3% fee)

### 14. `avg_swap_size_usd`
- **Description**: Average swap size estimate
- **Calculation**: `TVL × 0.01` (1% of TVL)
- **Example**: $30,864

### 15. `estimated_current_apy`
- **Description**: **TARGET VARIABLE** - Estimated current APY
- **Calculation**: `(fee_revenue / TVL) × (365 / days) × 100`
- **Example**: 14.2%
- **Note**: This becomes the label for ML training

---

## 🕸️ Network Centrality Features (3 features)

### 16. `betweenness_centrality`
- **Description**: How often pool lies on shortest paths between other pools
- **Calculation**: NetworkX `betweenness_centrality()`
- **Interpretation**: High = important "bridge" pool
- **Range**: 0.0 to 1.0
- **Example**: 0.234

### 17. `closeness_centrality`
- **Description**: How quickly pool can reach other pools in network
- **Calculation**: NetworkX `closeness_centrality()`
- **Interpretation**: High = central, accessible pool
- **Range**: 0.0 to 1.0
- **Example**: 0.567

### 18. `eigenvector_centrality`
- **Description**: Pool importance based on connections to other important pools
- **Calculation**: NetworkX `eigenvector_centrality()`
- **Interpretation**: High = connected to other important pools (like PageRank)
- **Range**: 0.0 to 1.0
- **Example**: 0.789

---

## 🔢 Metadata Features (3 features)

### 19. `contract`
- **Description**: Pool contract address
- **Source**: From transaction logs
- **Example**: 0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640

### 20. `timestamp`
- **Description**: When features were calculated
- **Format**: ISO 8601
- **Example**: 2024-01-15T14:30:00Z

### 21. `protocol`
- **Description**: DEX protocol (Uniswap V2/V3, Curve, etc.)
- **Source**: From transaction logs
- **Example**: "Uniswap V3"

---

## 🎯 Model Input Summary

### Features Used for Training (18 features)
```python
feature_columns = [
    # Financial (5)
    'current_tvl_eth',
    'current_tvl_usd',
    'eth_reserve',
    'fee_tier',
    'fee_percentage',

    # Volume (4)
    'tx_count',
    'unique_users',
    'activity_span',
    'avg_tx_per_block',

    # Revenue (3)
    'estimated_volume_usd',
    'estimated_fee_revenue',
    'avg_swap_size_usd',

    # Network (3)
    'betweenness_centrality',
    'closeness_centrality',
    'eigenvector_centrality',

    # Categorical (3) - needs encoding
    'paired_token',         # One-hot encode
    'protocol',            # One-hot encode
    'fee_tier'            # Can be used as continuous or categorical
]
```

### Target Variable (1 feature)
```python
target = 'estimated_current_apy'  # Continuous value (regression)
```

---

## 📊 Feature Importance (Expected)

Based on APY prediction logic, expected feature importance:

1. **`fee_percentage`** (HIGH) - Direct impact on revenue
2. **`estimated_volume_usd`** (HIGH) - More volume = more fees
3. **`tx_count`** (HIGH) - Activity indicator
4. **`current_tvl_usd`** (MEDIUM) - Denominator in APY calculation
5. **`betweenness_centrality`** (MEDIUM) - Popular routing pools have more volume
6. **`paired_token`** (MEDIUM) - Stablecoins may have different patterns
7. **`avg_tx_per_block`** (LOW) - Derivative of tx_count
8. **`unique_users`** (LOW) - Correlated with tx_count

---

## 🔬 Feature Engineering Pipeline

### Step 1: Raw Data Collection
```
Transaction Logs → Pool Addresses → Activity Metrics
```

### Step 2: Alchemy API Queries
```
Pool Address → Pool State (reserves, fees, tokens)
```

### Step 3: Calculated Features
```
Reserves + Price → TVL
Volume + Fees → Revenue
Revenue + TVL → APY
```

### Step 4: Network Analysis
```
Pool Connections → Centrality Metrics
```

### Step 5: Feature Normalization
```python
from sklearn.preprocessing import StandardScaler

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X[feature_columns])
```

---

## 🧪 Feature Validation

### Check for Missing Values
```python
print(df.isnull().sum())
```

### Check Distributions
```python
import matplotlib.pyplot as plt

df['estimated_current_apy'].hist(bins=50)
plt.xlabel('APY %')
plt.ylabel('Frequency')
plt.title('APY Distribution')
plt.show()
```

### Check Correlations
```python
import seaborn as sns

corr = df[feature_columns].corr()
sns.heatmap(corr, annot=True, cmap='coolwarm')
plt.title('Feature Correlation Matrix')
plt.show()
```

---

## 🚀 Usage Example

```python
from apy_features import calculate_all_features
import pandas as pd

# Load transaction logs
logs_df = pd.read_csv('updater/static/oneinch_logs_1D.csv')

# Calculate features for a specific pool
pool_address = "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640"
features = calculate_all_features(
    pool_address,
    logs_df,
    eth_price_usd=2500
)

print(f"Pool: {features['paired_token']}/ETH")
print(f"TVL: ${features['current_tvl_usd']:,.2f}")
print(f"Transactions: {features['tx_count']}")
print(f"Estimated APY: {features['estimated_current_apy']:.2f}%")
```

Output:
```
Pool: USDC/ETH
TVL: $45,234,567.89
Transactions: 1,234
Estimated APY: 12.5%
```

---

## 📝 Notes

- All Alchemy API calls include retry logic and rate limiting
- TVL calculations assume balanced pools (2x ETH reserve value)
- Volume estimates are conservative (1% of TVL per swap)
- APY estimates are based on recent activity and may not reflect future performance
- Network centrality features require full transaction graph construction
