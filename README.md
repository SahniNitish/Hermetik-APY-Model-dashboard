# Hermetik APY Model Dashboard

AI-powered liquidity pool growth prediction system for DeFi analytics.

## Components

| Folder | Description |
|--------|-------------|
| `apy-data-miner/` | AWS Lambda pipeline for collecting Uniswap V3 transaction data |
| `model/` | LightGBM ML model for predicting pool growth rates |
| `dashboard/` | FastAPI + React web dashboard for visualization |

## Quick Start

### 1. Train the Model

```bash
cd model
pip install numpy pandas lightgbm scikit-learn joblib
python hermetik_model.py train --forecast_horizon 1 --max_lag 7
```

### 2. Start the Dashboard

**Backend:**
```bash
cd dashboard/backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd dashboard/frontend
npm install
npm run dev
```

Open http://localhost:5173

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  apy-data-miner (AWS Lambda)                                │
│  └── Collects Uniswap V3 data → Features → CSV to S3        │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  model (LightGBM)                                           │
│  └── Loads training data → Trains → Makes predictions       │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  dashboard (FastAPI + React)                                │
│  └── API backend + Web UI to visualize predictions          │
└─────────────────────────────────────────────────────────────┘
```

## Tech Stack

- **Data Pipeline**: Node.js, AWS Lambda, PostgreSQL, S3
- **ML Model**: Python, LightGBM, pandas, scikit-learn
- **Backend**: FastAPI, uvicorn
- **Frontend**: React, Vite, Recharts

## Data Sources

- Ethereum blockchain via Alchemy API
- Uniswap V3 swap events
