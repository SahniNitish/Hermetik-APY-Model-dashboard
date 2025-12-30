# APY Data Miner

Automated data collection pipeline for Uniswap V3 swap transactions on Ethereum.

## Overview

This pipeline collects daily swap data from Uniswap V3 pools, processes it, and exports feature-engineered datasets for ML model training.

## Architecture

```
Ethereum (Alchemy API) → Collector Lambda → RDS PostgreSQL → Export Lambda → S3 CSV
```

**Schedule:**
| Time (UTC) | Action |
|------------|--------|
| 00:00 | Collect 24h of swap data |
| 00:30 | Export feature-engineered CSVs to S3 |

## Project Structure

```
├── infrastructure/          # AWS SAM deployment
│   ├── template.yaml       # CloudFormation template
│   ├── schema.sql          # Database schema
│   └── deploy.sh           # Deployment script
│
├── lambda/
│   ├── collector/          # Data collection Lambda
│   │   ├── index.mjs       # Main handler
│   │   └── lib/            # Modules (ethereum, database, classifier)
│   └── query/              # CSV export Lambda
│       └── index.mjs       # Export handler
│
└── updater/                # Local data fetching scripts
```

## Dataset Features (25 columns)

| Feature | Description |
|---------|-------------|
| `poolAddress` | Uniswap V3 pool contract address |
| `date` | Date of metrics |
| `tx_count` | Number of swap transactions |
| `unique_users` | Unique wallet addresses |
| `pool_name` | Token pair (e.g., WETH/USDT) |
| `token0Symbol`, `token1Symbol` | Token symbols |
| `fee`, `fee_percentage` | Pool fee tier |
| `poolType` | eth_paired, stablecoin, other |
| `tx_count_3d_avg` | 3-day rolling average |
| `tx_count_7d_avg` | 7-day rolling average |
| `tx_count_7d_std` | 7-day standard deviation |
| `tx_count_cumulative` | Cumulative transactions |
| `days_since_start` | Days since first tracked |
| `day_number` | Sequential day number |
| `tx_growth_rate` | Day-over-day growth |
| `target_tx_3d_ahead` | Target: tx count 3 days ahead |
| `target_tx_7d_ahead` | Target: tx count 7 days ahead |
| `stablecoin_pair_type` | stable_stable, stable_other, other |
| `activity_level` | high, medium, low |
| `pool_maturity` | new, young, mature, established |
| `volatility_level` | low_vol, medium_vol, high_vol |

## Deployment

```bash
cd infrastructure
./deploy.sh
```

## Access Data

```bash
# Download latest dataset from S3
aws s3 cp s3://apy-data-miner-exports-226208942523/pool_dataset_latest.csv ./

# Download training/test splits
aws s3 cp s3://apy-data-miner-exports-226208942523/pool_training_data_latest.csv ./
aws s3 cp s3://apy-data-miner-exports-226208942523/pool_test_data_latest.csv ./
```

## Tech Stack

- AWS Lambda (Node.js 18.x)
- AWS RDS PostgreSQL
- AWS S3
- AWS EventBridge
- Alchemy API (Ethereum)

## License

MIT
