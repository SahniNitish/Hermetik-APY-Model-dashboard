# 📊 Pool Performance Prediction Dataset

**For:** Nolan (Model Training)
**From:** Data Pipeline
**Date:** November 2, 2025
**Dataset:** 30 Days of Ethereum Pool Data

---

## 🎯 Goal

**Predict which pools will have the highest transaction activity** in 3-7 days.

Use this data to train a regression model that forecasts future pool performance based on historical patterns.

---

## 📁 Files for You

### Main Training Files
```
pool_training_data.csv    - 37,112 rows for training your model
pool_test_data.csv        - 11,826 rows for validation
pool_full_dataset.csv     - Complete dataset (61,798 rows)
```

### Reference Files
```
updater/static/pool_metadata.csv         - Pool information (tokens, fees, types)
updater/static/pool_logs_30d_*.csv       - Raw transaction data (7.2M txs)
```

---

## 📊 Dataset Overview

**Training Set:**
- **37,112 rows** (pool-day combinations)
- **2,333 unique pools**
- **Date range:** Oct 2 - Oct 26, 2025
- **Target:** Predict transaction counts 3 & 7 days ahead

**Test Set:**
- **11,826 rows**
- **3,330 unique pools**
- **Date range:** Oct 27 - Nov 2, 2025

---

## 🔢 Features (Input Variables)

### Activity Metrics
1. **tx_count** - Number of transactions today
2. **unique_users** - Number of unique wallet addresses today
3. **tx_count_cumulative** - Total transactions since pool started

### Rolling Averages (Trends)
4. **tx_count_3d_avg** - Average transactions over last 3 days
5. **tx_count_7d_avg** - Average transactions over last 7 days
6. **tx_count_7d_std** - Volatility (standard deviation) over 7 days

### Growth Indicators
7. **tx_growth_rate** - Percent change vs yesterday
8. **days_since_start** - Days since first transaction in dataset

### Pool Characteristics
9. **fee_percentage** - Pool fee (0.0005 = 0.05%, 0.003 = 0.3%, 0.01 = 1%)
10. **poolType** - Pool category (eth_paired, stablecoin, other)

### Metadata
- **pool_name** - Token pair (e.g., "USDC/WETH")
- **token0Symbol**, **token1Symbol** - Individual token symbols
- **date** - Date of observation
- **day_number** - Day number in sequence (1-30)

---

## 🎯 Target Variables (What to Predict)

Choose one or more targets to predict:

### Single Day Prediction
1. **target_tx_3d_ahead** - Transaction count exactly 3 days from now
2. **target_tx_7d_ahead** - Transaction count exactly 7 days from now

### Average Period Prediction (Recommended)
3. **target_tx_3d_avg_ahead** - Average daily transactions over next 3 days
4. **target_tx_7d_avg_ahead** - Average daily transactions over next 7 days

**Recommendation:** Use `target_tx_7d_avg_ahead` for best results (smoother, less noisy).

---

## 🚀 Quick Start - Train a Model

```python
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score

# Load training data
train = pd.read_csv('pool_training_data.csv')

# Select features
feature_cols = [
    'tx_count',
    'unique_users',
    'tx_count_3d_avg',
    'tx_count_7d_avg',
    'tx_count_7d_std',
    'tx_count_cumulative',
    'days_since_start',
    'tx_growth_rate',
    'fee_percentage'
]

# One-hot encode pool type
train_encoded = pd.get_dummies(train, columns=['poolType'])

# Update feature cols to include encoded pool types
feature_cols_encoded = feature_cols + [col for col in train_encoded.columns if col.startswith('poolType_')]

# Prepare data
X = train_encoded[feature_cols_encoded]
y = train_encoded['target_tx_7d_avg_ahead']  # Predict 7-day average

# Split for validation
X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)

# Train model
model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
model.fit(X_train, y_train)

# Evaluate
y_pred = model.predict(X_val)
mae = mean_absolute_error(y_val, y_pred)
r2 = r2_score(y_val, y_pred)

print(f"Mean Absolute Error: {mae:.2f} transactions")
print(f"R² Score: {r2:.3f}")

# Feature importance
importance_df = pd.DataFrame({
    'feature': feature_cols_encoded,
    'importance': model.feature_importances_
}).sort_values('importance', ascending=False)

print("\nTop 5 Features:")
print(importance_df.head())
```

---

## 📈 Expected Performance

### Baseline Metrics
- **MAE:** ~50-100 transactions (depends on pool size)
- **R² Score:** 0.65-0.85 (good is > 0.7)

### Model Comparison

| Model | Expected R² | Training Time |
|-------|-------------|---------------|
| Random Forest | 0.75-0.85 | Medium |
| XGBoost | 0.78-0.88 | Medium |
| Linear Regression | 0.50-0.65 | Fast |
| Neural Network | 0.70-0.80 | Slow |

**Recommendation:** Start with Random Forest, then try XGBoost for better performance.

---

## 🏆 Top Performing Pools (Reference)

These pools had highest average daily transactions:

1. **WETH/USDT** (ETH pool) - 5,810 avg daily txs
2. **USDC/WETH** (ETH pool) - 4,381 avg daily txs
3. **APEX/USDT** (Other) - 2,142 avg daily txs
4. **WETH/PNKSTR** (ETH pool) - 1,421 avg daily txs
5. **TRX/WETH** (ETH pool) - 1,349 avg daily txs

---

## 🔍 Data Exploration

```python
import pandas as pd
import matplotlib.pyplot as plt

# Load data
train = pd.read_csv('pool_training_data.csv')

# Top pools by total transactions
top_pools = train.groupby('pool_name')['tx_count'].sum().nlargest(10)
print("Top 10 Pools:")
print(top_pools)

# Pool type distribution
print("\nPool Type Distribution:")
print(train['poolType'].value_counts())

# Transaction trends over time
train['date'] = pd.to_datetime(train['date'])
daily_totals = train.groupby('date')['tx_count'].sum()

plt.figure(figsize=(12, 5))
plt.plot(daily_totals)
plt.title('Total Daily Transactions Across All Pools')
plt.xlabel('Date')
plt.ylabel('Total Transactions')
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig('transaction_trends.png')
plt.show()
```

---

## 💡 Tips for Better Models

### Feature Engineering Ideas
1. **Day of week** - Some pools may have weekly patterns
   ```python
   train['day_of_week'] = pd.to_datetime(train['date']).dt.dayofweek
   ```

2. **Pool age** - Older pools may be more stable
   ```python
   # Already have: days_since_start
   ```

3. **Relative volatility** - Compare pool's volatility to average
   ```python
   avg_vol = train['tx_count_7d_std'].mean()
   train['volatility_ratio'] = train['tx_count_7d_std'] / avg_vol
   ```

4. **Fee tier categories** - Group pools by fee level
   ```python
   train['fee_category'] = pd.cut(train['fee_percentage'], bins=[0, 0.001, 0.005, 1], labels=['low', 'medium', 'high'])
   ```

### Model Improvements
1. **Hyperparameter tuning** - Use GridSearchCV
2. **Ensemble methods** - Combine multiple models
3. **Time-series specific models** - Try Prophet or ARIMA for individual pools
4. **Pool segmentation** - Train separate models for ETH pools, stablecoins, and others

---

## 🎓 Understanding the Data

### What Each Row Represents
Each row = One pool on one specific day

Example:
```
Row 1: USDC/WETH on Oct 5
  - Had 1,234 transactions today
  - 7-day average: 1,100 transactions
  - Target: Will have 1,400 transactions on Oct 12
```

### How to Use Predictions
After training, you can:
1. **Predict future activity** for existing pools
2. **Identify trending pools** (high growth rate + high predicted future activity)
3. **Compare pool types** (are ETH pools more predictable than others?)
4. **Find investment opportunities** (pools with increasing activity = more fees/APY)

---

## ❓ FAQ

**Q: Why predict transaction count instead of APY?**
A: Transaction count is a strong proxy for pool performance. More transactions = more fees = higher APY. It's also easier to predict accurately than APY itself.

**Q: Can I use this for live trading?**
A: This is historical data for training. For live predictions, you'd need to:
1. Collect fresh data daily
2. Run predictions on new data
3. Update your model periodically

**Q: What if a pool has missing days?**
A: Some pools don't have transactions every day. The model should handle this - just ensure your features account for gaps (e.g., use `days_since_start` instead of assuming consecutive days).

**Q: How do I deploy this model?**
A: After training:
1. Save model: `joblib.dump(model, 'pool_predictor.pkl')`
2. Load for predictions: `model = joblib.load('pool_predictor.pkl')`
3. Create API or automated pipeline

---

## 📞 Next Steps

1. **Load the data** - Start with `pool_training_data.csv`
2. **Explore** - Run the quick start code
3. **Train baseline model** - RandomForestRegressor
4. **Evaluate** - Check MAE and R²
5. **Iterate** - Try different features and models
6. **Share results** - Let us know what R² score you achieve!

---

## 📊 Dataset Statistics Summary

```
Total Data Collected:      7,188,733 transactions
Date Range:                Oct 2 - Nov 2, 2025 (32 days)
Unique Pools:              6,131
Pools with 20+ days:       1,526
Pools with 30 full days:   237

Training Rows:             37,112
Test Rows:                 11,826
Features:                  10
Targets:                   4 (choose 1)

Pool Types:
  - ETH-paired:            71.3%
  - Stablecoins:           0.4%
  - Other tokens:          28.3%
```

---

**Good luck with your model training, Nolan! 🚀**

If you have questions, check the code in:
- `generate_timeseries_features.py` - How features were created
- `create_training_dataset.py` - How targets were generated
