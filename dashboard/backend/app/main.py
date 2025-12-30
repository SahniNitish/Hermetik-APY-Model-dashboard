from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import pandas as pd
import numpy as np
import joblib
import json
from pathlib import Path

app = FastAPI(title="APY Prediction API", version="1.0.0")

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths
MODEL_DIR = Path(__file__).parent.parent.parent.parent / "model"
DATA_DIR = Path(__file__).parent.parent.parent.parent

# Global model cache
model_cache = {}
contracts_cache = {}


class PredictionRequest(BaseModel):
    max_lag: int = 7
    forecast_horizon: int = 1
    top_n: int = 10


class PoolPrediction(BaseModel):
    rank: int
    pool_address: str
    predicted_growth_rate: float
    current_tx_count: Optional[float] = None
    fee_percentage: Optional[float] = None


class PredictionResponse(BaseModel):
    predictions: list[PoolPrediction]
    prediction_date: str
    forecast_horizon: int
    total_pools: int


def load_contracts_mapping(max_lag: int) -> dict:
    """Load contracts mapping from JSON."""
    if max_lag in contracts_cache:
        return contracts_cache[max_lag]

    contracts_path = MODEL_DIR / f"contracts_{max_lag}.json"
    if not contracts_path.exists():
        return {}

    with open(contracts_path, "r") as f:
        contracts = json.load(f)

    # Reverse mapping: int -> address
    reverse_contracts = {v: k for k, v in contracts.items()}
    contracts_cache[max_lag] = reverse_contracts
    return reverse_contracts


def load_model(max_lag: int, forecast_horizon: int):
    """Load trained model from disk."""
    cache_key = f"{forecast_horizon}_{max_lag}"
    if cache_key in model_cache:
        return model_cache[cache_key]

    model_path = MODEL_DIR / f"growth_model_{forecast_horizon}_{max_lag}.pkl"
    if not model_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Model not found. Train first with: python hermetik_model.py train --forecast_horizon {forecast_horizon} --max_lag {max_lag}"
        )

    model = joblib.load(model_path)
    model_cache[cache_key] = model
    return model


def build_features(df_features: pd.DataFrame, max_lag: int = 7) -> pd.DataFrame:
    """Build features for prediction (mirrors hermetik_model.py logic)."""
    df_features = df_features.copy()

    # Log transform tx count
    df_features['tx_transform'] = np.log(df_features['tx_count'] + 1)

    # Growth rate
    df_features['growth_rate'] = (
        df_features
        .groupby('poolAddress')['tx_transform']
        .diff()
    )

    # Lag features
    for k in range(1, max_lag + 1):
        df_features[f'lag_{k}'] = (
            df_features
            .groupby('poolAddress')['growth_rate']
            .shift(k)
        )

    # Rolling means
    rolling_list = [3, 5, 7, 14]
    for i in rolling_list:
        df_features[f'rolling_mean_{i}d'] = (
            df_features
            .groupby('poolAddress', group_keys=False)['growth_rate']
            .transform(lambda s: s.shift(1).rolling(window=i, min_periods=1).mean())
        )

    # Load contracts mapping
    contracts_path = MODEL_DIR / f"contracts_{max_lag}.json"
    if contracts_path.exists():
        with open(contracts_path, "r") as f:
            contracts_dic = json.load(f)
        df_features['contract'] = df_features['poolAddress'].map(contracts_dic).fillna(-1).astype(int)
    else:
        raise HTTPException(status_code=404, detail="Contracts mapping not found. Train model first.")

    # Select columns
    cols = ['contract', 'date', 'tx_count', 'fee_percentage', 'tx_count_cumulative',
            'growth_rate', 'day_number', 'tx_transform']
    for k in range(1, max_lag + 1):
        cols.append(f'lag_{k}')
    for i in rolling_list:
        cols.append(f'rolling_mean_{i}d')

    df_features = df_features[cols].copy()

    # Convert date to ordinal
    df_features['date'] = pd.to_datetime(df_features['date']).map(pd.Timestamp.toordinal)
    df_features = df_features.sort_values('date')

    return df_features


def filter_dataset(df_dataset: pd.DataFrame) -> pd.DataFrame:
    """Keep pools that have entries for every day."""
    dates = df_dataset['date'].unique()
    intersec = set(df_dataset['poolAddress'].unique())
    for date in dates:
        df_date = df_dataset[df_dataset['date'] == date]
        contracts_date = set(df_date['poolAddress'].unique())
        intersec = intersec.intersection(contracts_date)

    return df_dataset[df_dataset['poolAddress'].isin(intersec)]


@app.get("/")
async def root():
    return {"message": "APY Prediction API", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/api/models")
async def list_models():
    """List available trained models."""
    models = list(MODEL_DIR.glob("growth_model_*.pkl"))
    available = []
    for m in models:
        name = m.stem.replace("growth_model_", "")
        parts = name.split("_")
        if len(parts) == 2:
            available.append({
                "forecast_horizon": int(parts[0]),
                "max_lag": int(parts[1]),
                "path": str(m)
            })
    return {"models": available}


@app.post("/api/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest):
    """Get pool growth predictions."""
    # Load data
    data_path = DATA_DIR / "pool_dataset_latest.csv"
    if not data_path.exists():
        # Try apy-data-miner exports
        data_path = DATA_DIR / "apy-data-miner" / "exports" / "pool_dataset_latest.csv"

    if not data_path.exists():
        raise HTTPException(status_code=404, detail="Dataset not found")

    df = pd.read_csv(data_path)
    original_df = df.copy()

    # Filter and build features
    df = filter_dataset(df)
    df_features = build_features(df, request.max_lag)

    # Get most recent date for prediction
    pred_date = df_features["date"].max()
    df_pred = df_features[df_features["date"] == pred_date].copy()

    if df_pred.empty:
        raise HTTPException(status_code=400, detail="No data available for prediction")

    # Load model and predict
    model = load_model(request.max_lag, request.forecast_horizon)
    preds = model.predict(df_pred)
    df_pred.loc[:, "predictions"] = preds

    # Rank predictions
    df_pred['rank'] = df_pred['predictions'].rank(ascending=False).astype(int)
    df_pred = df_pred.sort_values('rank')

    # Get contract address mapping
    reverse_contracts = load_contracts_mapping(request.max_lag)

    # Build response
    predictions = []
    for i, row in df_pred.head(request.top_n).iterrows():
        contract_id = int(row['contract'])
        pool_address = reverse_contracts.get(contract_id, f"Unknown ({contract_id})")

        predictions.append(PoolPrediction(
            rank=int(row['rank']),
            pool_address=pool_address,
            predicted_growth_rate=float(row['predictions']),
            current_tx_count=float(row['tx_count']) if pd.notna(row['tx_count']) else None,
            fee_percentage=float(row['fee_percentage']) if pd.notna(row.get('fee_percentage')) else None,
        ))

    # Convert ordinal date back to string
    from datetime import date
    pred_date_str = date.fromordinal(int(pred_date)).isoformat()

    return PredictionResponse(
        predictions=predictions,
        prediction_date=pred_date_str,
        forecast_horizon=request.forecast_horizon,
        total_pools=len(df_pred)
    )


@app.get("/api/pools")
async def list_pools():
    """List all available pools with metadata."""
    data_path = DATA_DIR / "pool_dataset_latest.csv"
    if not data_path.exists():
        data_path = DATA_DIR / "apy-data-miner" / "exports" / "pool_dataset_latest.csv"

    if not data_path.exists():
        raise HTTPException(status_code=404, detail="Dataset not found")

    df = pd.read_csv(data_path)

    # Get unique pools with their latest stats
    latest_date = df['date'].max()
    df_latest = df[df['date'] == latest_date]

    pools = []
    for _, row in df_latest.iterrows():
        pools.append({
            "pool_address": row['poolAddress'],
            "pool_name": row.get('pool_name', 'Unknown'),
            "token0": row.get('token0Symbol', ''),
            "token1": row.get('token1Symbol', ''),
            "fee_percentage": row.get('fee_percentage'),
            "pool_type": row.get('poolType', ''),
            "tx_count": row.get('tx_count'),
        })

    return {"pools": pools, "total": len(pools), "date": latest_date}


@app.get("/api/pool/{pool_address}/history")
async def pool_history(pool_address: str):
    """Get historical data for a specific pool."""
    data_path = DATA_DIR / "pool_dataset_latest.csv"
    if not data_path.exists():
        data_path = DATA_DIR / "apy-data-miner" / "exports" / "pool_dataset_latest.csv"

    if not data_path.exists():
        raise HTTPException(status_code=404, detail="Dataset not found")

    df = pd.read_csv(data_path)
    df_pool = df[df['poolAddress'] == pool_address].sort_values('date')

    if df_pool.empty:
        raise HTTPException(status_code=404, detail="Pool not found")

    history = []
    for _, row in df_pool.iterrows():
        history.append({
            "date": row['date'],
            "tx_count": row.get('tx_count'),
            "unique_users": row.get('unique_users'),
            "tx_count_cumulative": row.get('tx_count_cumulative'),
        })

    return {
        "pool_address": pool_address,
        "pool_name": df_pool.iloc[0].get('pool_name', 'Unknown'),
        "history": history
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
