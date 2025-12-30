# Hermetik Prediction Model

LightGBM-based machine learning model for predicting liquidity pool growth rates.

## Overview

This model predicts future transaction volume growth for Uniswap V3 liquidity pools using historical transaction patterns and engineered features.

## Installation

```bash
pip install numpy pandas lightgbm scikit-learn joblib
```

On macOS, you may also need:
```bash
brew install libomp
```

## Usage

### Train the Model

```bash
python hermetik_model.py train --forecast_horizon 1 --max_lag 7
```

**Parameters:**
- `--forecast_horizon`: Days ahead to predict (1, 3, or 7)
- `--max_lag`: Number of lag days for features (7 or 14)

### Make Predictions

```bash
python hermetik_model.py predict --forecast_horizon 1 --max_lag 7
```

## Input Data

The model expects `pool_dataset_latest.csv` with these columns:
- `poolAddress` - Pool contract address
- `date` - Date of observation
- `tx_count` - Daily transaction count
- `fee_percentage` - Pool fee tier
- `tx_count_cumulative` - Cumulative transactions
- `day_number` - Sequential day number

## Features Generated

The model automatically generates:
- `growth_rate` - Log-transformed daily growth
- `lag_1` to `lag_7` - Lagged growth rates
- `rolling_mean_3d/5d/7d/14d` - Rolling averages

## Output Files

After training:
- `growth_model_{horizon}_{lag}.pkl` - Trained model
- `contracts_{lag}.json` - Pool address mapping

## Model Details

| Attribute | Value |
|-----------|-------|
| Algorithm | LightGBM Regressor |
| Loss Function | Huber (robust to outliers) |
| Validation | 10% holdout, no shuffle |
| Early Stopping | 10 rounds |

## Example Output

```
Top 5 pools for predicted growth rate on 2025-11-02:
Pool 1: poolAddress = 0x88e6..., predicted growth rate = 1.08
Pool 2: poolAddress = 0x1c98..., predicted growth rate = 1.05
...
```
