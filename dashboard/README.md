# Hermetik Dashboard

Web dashboard for visualizing liquidity pool growth predictions.

## Stack

- **Backend**: FastAPI (Python)
- **Frontend**: React + Vite
- **Charts**: Recharts
- **Styling**: Custom CSS (Hermetik brand theme)

## Installation

### Backend

```bash
cd backend
pip install -r requirements.txt
```

### Frontend

```bash
cd frontend
npm install
```

## Running the Dashboard

### 1. Start Backend (Terminal 1)

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

Backend runs at: http://localhost:8000

### 2. Start Frontend (Terminal 2)

```bash
cd frontend
npm run dev
```

Frontend runs at: http://localhost:5173

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/predict` | POST | Get pool growth predictions |
| `/api/pools` | GET | List all tracked pools |
| `/api/pool/{address}/history` | GET | Get pool historical data |
| `/api/models` | GET | List available trained models |
| `/health` | GET | Health check |

### Prediction Request

```json
POST /api/predict
{
  "max_lag": 7,
  "forecast_horizon": 1,
  "top_n": 10
}
```

### Response

```json
{
  "predictions": [
    {
      "rank": 1,
      "pool_address": "0x88e6...",
      "predicted_growth_rate": 1.08,
      "current_tx_count": 245,
      "fee_percentage": 0.003
    }
  ],
  "prediction_date": "2025-11-02",
  "forecast_horizon": 1,
  "total_pools": 17
}
```

## Features

- **Prediction Settings**: Configure forecast horizon, analysis depth, pool count
- **Stats Overview**: Pools analyzed, forecast window, top growth rate
- **Predictions Table**: Ranked pools with growth rates, links to Etherscan
- **Growth Chart**: Bar chart comparing top pools
- **Pool History**: Line chart for individual pool transaction history

## Project Structure

```
dashboard/
├── backend/
│   ├── app/
│   │   └── main.py          # FastAPI application
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── App.jsx          # Main React component
    │   ├── App.css          # Hermetik brand styling
    │   └── main.jsx         # Entry point
    ├── package.json
    └── vite.config.js
```

## Environment

The backend expects the model files in `../model/`:
- `growth_model_1_7.pkl`
- `contracts_7.json`
- `pool_dataset_latest.csv`

## Brand Colors

- Green: `#00321d`
- Gold: `#B2A534`
- Font: DM Sans, Crimson Text
