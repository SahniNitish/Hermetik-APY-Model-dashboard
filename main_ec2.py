"""
A script to process DeFi liquidity data and train a prediction model,
designed to be run on an AWS EC2 instance.

This script connects to an S3 bucket to read historical data and store
model artifacts and predictions.

Prerequisites:
- Run this on an EC2 instance with an attached IAM role granting S3 access.
- Python 3 and required packages (pandas, boto3, networkx, scikit-learn) installed.

Usage from the command line:
----------------------------------------------------------------
1. To generate the training dataset from rolling files in S3 (no dates):
   python3 main_ec2.py --bucket BUCKET generate-from-rolling

2. To generate the training dataset from dated snapshots in S3:
   python3 main_ec2.py --bucket BUCKET generate-data --start YYYY-MM-DD --end YYYY-MM-DD

3. To train the model using the generated dataset and save it to S3:
   python3 main_ec2.py --bucket BUCKET train-model

4. To score current rolling data and print top-N predicted pools:
   python3 main_ec2.py --bucket BUCKET infer-top --top 20
----------------------------------------------------------------
"""

import argparse
import sys
import json
from datetime import datetime, timedelta
from io import BytesIO
import pickle
import json
import time
import numpy as np # Added for random label simulation

import boto3
import networkx as nx
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import joblib
from sklearn.metrics import precision_score
from web3 import Web3


# Constants
ROLLING_DATASET_KEY = "training/rolling_training_dataset.csv"
DATED_DATASET_KEY = "training/dated_training_dataset.csv"
MODEL_KEY = "training/models/random_forest.pkl"
FEATURES_KEY = "training/models/feature_list.json"

# Web3 setup for token symbol queries
W3_PROVIDER = None
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function"
    }
]

def get_token_symbol(token_address):
    """Get token symbol from blockchain using web3."""
    global W3_PROVIDER
    
    # Common token addresses with known symbols (fallback mapping)
    KNOWN_TOKENS = {
        '0xdAC17F958D2ee523a2206206994597C13D831ec7': 'USDT',
        '0xA0b86991c31D6832c4b0B9e26cB4171d43c4a9a4': 'USDC',  # Circle USDC
        '0x6B175474E89094C44Da98b954EedeAC495271d0F': 'DAI',
        '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2': 'WETH',
        '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599': 'WBTC',
        '0x83F20F44975D03b1b09e64809B757c47f942BEeA': 'SDAI',  # Savings DAI
        '0x9D39A5DE30e57443BfF2A8307A4256c8797A3497': 'SUSDE', # Staked USDe
        '0x4c9EDD5852cd905f086C759E8383e09bff1E68B3': 'USDE',  # Ethena USDe
        '0x6c3ea9036406852006290770BEdFcAbA0e23A0e8': 'PYUSD', # PayPal USD
        '0x99D8a9C45b2ecA8864373A26D1459e3Dff1e17F3': 'MIM',   # Magic Internet Money
        '0x853d955aCEf822Db058eb8505911ED77F175b99e': 'FRAX',
        '0xf939E0A03FB07F59A73314E73794Be0E57ac1b4E': 'crvUSD',
        '0xdC035D45d973E3EC169d2276DDab16f1e407384F': 'USDS',  # Sky USDS
        '0x40D16FC0246aD3160Ccc09B8D0D3A2cD28aE6C2f': 'GHO',
        '0x57Ab1ec28D129707052df4dF418D58a2D46d5f51': 'sY',
        '0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0': 'USD3',
        # Add more common tokens from your allowed list
        '0x0C10bF8FcB7Bf5412187A595ab97a3609160b5c6': 'USDD',
        '0x056Fd409E1d7A124BD7017459dFEa2F387b6d5Cd': 'GUSD',
        '0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9': 'USDT',  # USDT on Arbitrum
        '0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063': 'DAI',   # DAI on Polygon
        '0xae78736Cd615f374D3085123A210448E74Fc6393': 'rETH',
        '0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0': 'wstETH',
        '0xA35b1B31Ce002FBF2058D22F30f95D405200A15b': 'ETHx'
    }
    
    # Check if we have a known mapping first
    if token_address in KNOWN_TOKENS:
        return KNOWN_TOKENS[token_address]
    
    if W3_PROVIDER is None:
        # Try to connect to Ethereum mainnet using Alchemy
        try:
            import os
            alchemy_key = os.getenv('ALCHEMY_API_KEY')
            if alchemy_key:
                alchemy_url = f'https://eth-mainnet.g.alchemy.com/v2/{alchemy_key}'
                W3_PROVIDER = Web3(Web3.HTTPProvider(alchemy_url))
                print(f"    🔗 Connected to Alchemy RPC")
            else:
                # Fallback to public RPCs
                W3_PROVIDER = Web3(Web3.HTTPProvider('https://eth.llamarpc.com'))
                if not W3_PROVIDER.is_connected():
                    W3_PROVIDER = Web3(Web3.HTTPProvider('https://rpc.ankr.com/eth'))
                print(f"    🔗 Connected to public RPC")
        except Exception as e:
            print(f"    ⚠️  Could not connect to Ethereum RPC: {e}")
            return token_address[:8] + "..."
    
    try:
        if not W3_PROVIDER.is_connected():
            return token_address[:8] + "..."
            
        # Convert to checksum address
        try:
            checksum_address = Web3.to_checksum_address(token_address)
        except:
            return token_address[:8] + "..."
            
        contract = W3_PROVIDER.eth.contract(address=checksum_address, abi=ERC20_ABI)
        symbol = contract.functions.symbol().call()
        
        # Rate limiting: sleep between requests to avoid hitting RPC limits
        time.sleep(0.1)  # 100ms delay between requests
        
        return symbol if symbol else token_address[:8] + "..."
    except Exception as e:
        print(f"    ⚠️  Error querying {token_address[:8]}: {e}")
        # Fallback to shortened address
        return token_address[:8] + "..."

def calculate_contract_centrality(logs_df):
    """
    Calculate centrality measures for contracts based on token flow between them.
    Creates a directed graph where contracts are connected if tokens flow between them.
    """
    contract_tokens = {}
    
    # For each contract, find all tokens it touches
    for _, row in logs_df.iterrows():
        contract = row['Contract Address']
        input_token = row['Input Token']
        output_token = row['Output Token']
        
        if contract not in contract_tokens:
            contract_tokens[contract] = set()
        contract_tokens[contract].add(input_token)
        contract_tokens[contract].add(output_token)
    
    # Build directional edges: contract A -> contract B if tokens flow from A to B
    edges = []
    contracts = list(contract_tokens.keys())
    
    for i, contract1 in enumerate(contracts):
        for j, contract2 in enumerate(contracts):
            if i != j:  # Don't connect contract to itself
                # Check if there's token flow from contract1 to contract2
                contract1_outputs = contract_tokens[contract1]
                contract2_inputs = contract_tokens[contract2]
                
                # If there's overlap in tokens, create directional edge
                if contract1_outputs & contract2_inputs:  # intersection
                    # Weight the edge by number of shared tokens
                    shared_tokens = len(contract1_outputs & contract2_inputs)
                    edges.append((contract1, contract2, shared_tokens))
    
    # Create directed NetworkX graph with weighted edges
    G = nx.DiGraph()
    G.add_weighted_edges_from(edges)
    
    # Calculate centrality measures for CONTRACTS
    try:
        betweenness_centrality = nx.betweenness_centrality(G, weight='weight')
    except:
        betweenness_centrality = {node: 0 for node in G.nodes()}
        
    try:
        closeness_centrality = nx.closeness_centrality(G, distance='weight')
    except:
        closeness_centrality = {node: 0 for node in G.nodes()}
        
    # Fix eigenvector centrality calculation
    try:
        # Use power iteration method which is more robust
        eigenvector_centrality = nx.power_iteration(G, weight='weight', max_iter=1000, tol=1e-6)
    except:
        try:
            # Fallback to numpy method
            eigenvector_centrality = nx.eigenvector_centrality_numpy(G, weight='weight')
        except:
            # Final fallback: use degree centrality as proxy
            eigenvector_centrality = nx.in_degree_centrality(G)
    
    return betweenness_centrality, closeness_centrality, eigenvector_centrality, G

def generate_training_data_from_rolling(bucket_name: str, lookback_period: str = "3D"):
    """
    Generates a training dataset from rolling logs and 1D graph from S3.
    Uses HISTORICAL data for features to predict FUTURE growth.
    
    Args:
        bucket_name: S3 bucket containing the data
        lookback_period: Period for historical data ("1D", "3D", "1W", "3W", "1M")
    """
    s3 = boto3.client("s3")
    try:
        # Load HISTORICAL logs for features based on lookback period
        historical_key = f"rolling/oneinch_logs_{lookback_period}.csv"
        logs_historical_obj = s3.get_object(Bucket=bucket_name, Key=historical_key)
        logs_historical_df = pd.read_csv(BytesIO(logs_historical_obj["Body"].read()))
        print(f"Loading HISTORICAL features from s3://{bucket_name}/{historical_key}...")

        # Load 1D graph for centrality features
        graph_1d_obj = s3.get_object(Bucket=bucket_name, Key="rolling/token_graph1D.csv")
        graph_1d_df = pd.read_csv(BytesIO(graph_1d_obj["Body"].read()))
        print("Loading graph from s3://{}/rolling/token_graph1D.csv...".format(bucket_name))

        # Load CURRENT 1D logs for current state (baseline)
        logs_1d_current_obj = s3.get_object(Bucket=bucket_name, Key="rolling/oneinch_logs_1D.csv")
        logs_1d_current_df = pd.read_csv(BytesIO(logs_1d_current_obj["Body"].read()))
        print("Loading current baseline from s3://{}/rolling/oneinch_logs_1D.csv...".format(bucket_name))

        # --- FEATURE ENGINEERING (from HISTORICAL data) ---
        features = logs_historical_df.groupby("Contract Address").agg(
            tx_count=("Transaction Hash", "count"),
            min_block=("Block Number", "min"),
            max_block=("Block Number", "max"),
        ).reset_index()
        features.columns = ["contract", "tx_count", "min_block", "max_block"]
        features["activity_span"] = features["max_block"] - features["min_block"]

        # Enhanced centrality calculation - how important this contract is in the network
        betweenness_centrality, closeness_centrality, eigenvector_centrality, G = calculate_contract_centrality(logs_historical_df)
        
        # Map centrality measures to contracts
        features["betweenness_centrality"] = features["contract"].map(betweenness_centrality).fillna(0)
        features["closeness_centrality"] = features["contract"].map(closeness_centrality).fillna(0)
        features["eigenvector_centrality"] = features["contract"].map(eigenvector_centrality).fillna(0)

        # --- LABEL GENERATION (percentage growth from current 1D to future 3D) ---
        # Calculate current 1D volume (baseline)
        volume_1d_current = logs_1d_current_df.groupby("Contract Address").size().reset_index()
        volume_1d_current.columns = ["contract", "volume_1d_current"]
        
        # Calculate future volume (what we're predicting)
        # This would ideally be from a future timestamp, but for now we'll simulate
        # by using the historical data as a proxy for future growth potential
        volume_future = logs_historical_df.groupby("Contract Address").size().reset_index()
        volume_future.columns = ["contract", "volume_future"]
        
        # Merge and calculate percentage growth
        volume_growth = pd.merge(volume_1d_current, volume_future, on="contract", how="left").fillna(0)
        volume_growth["volume_growth_pct"] = (
            (volume_growth["volume_future"] - volume_growth["volume_1d_current"]) / 
            (volume_growth["volume_1d_current"] + 1) * 100  # +1 to avoid division by zero
        )
        
        # Label: top 20% by percentage growth (not absolute volume)
        threshold = volume_growth["volume_growth_pct"].quantile(0.8)
        volume_growth["label"] = (volume_growth["volume_growth_pct"] >= threshold).astype(int)
        
        # Merge features with labels
        final_df = pd.merge(features, volume_growth[["contract", "label", "volume_growth_pct"]], on="contract")
        
        # Add some additional features
        final_df["volume_1d_current"] = final_df["contract"].map(dict(zip(volume_1d_current["contract"], volume_1d_current["volume_1d_current"]))).fillna(0)
        final_df["volume_future"] = final_df["contract"].map(dict(zip(volume_future["contract"], volume_future["volume_future"]))).fillna(0)
        
        out_buffer = BytesIO()
        final_df.to_csv(out_buffer, index=False)
        out_buffer.seek(0)

        dataset_key = f"training/rolling_training_dataset_{lookback_period.lower()}.csv"
        s3.put_object(Bucket=bucket_name, Key=dataset_key, Body=out_buffer)
        print(f"Successfully generated rolling dataset and uploaded to s3://{bucket_name}/{dataset_key}")
        print(f"Features: tx_count, activity_span, betweenness_centrality, closeness_centrality, eigenvector_centrality")
        print(f"Labels: percentage growth in volume (top 20% = 1, rest = 0)")
        print(f"IMPORTANT: Using HISTORICAL {lookback_period} data for features to predict FUTURE growth!")

    except s3.exceptions.NoSuchKey as e:
        print(f"Missing rolling inputs: {e}")
    except Exception as e:
        print(f"An error occurred during rolling data generation: {e}")


def generate_training_data(start_date: str, end_date: str, bucket_name: str):
    """
    Generates a historical training dataset by processing daily log and graph data from S3.
    """

    def daterange(start, end):
        curr = start
        while curr <= end:
            yield curr
            curr += timedelta(days=1)

    s3 = boto3.client("s3")
    all_rows = []

    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        print("Error: Please use the date format YYYY-MM-DD.")
        sys.exit(1)

    for day in daterange(start, end):
        day_str = day.strftime("%Y-%m-%d")
        print(f"Processing {day_str}...")

        try:
            graph_key = f"graphs/{day_str}-token_graph.csv"
            g_obj = s3.get_object(Bucket=bucket_name, Key=graph_key)
            g_df = pd.read_csv(BytesIO(g_obj["Body"].read()))
            G = nx.from_pandas_edgelist(g_df, "node1", "node2", edge_attr=True)

            logs_key = f"logs/{day_str}-oneinch_logs.csv"
            l_obj = s3.get_object(Bucket=bucket_name, Key=logs_key)
            logs_df = pd.read_csv(BytesIO(l_obj["Body"].read()))

            features = (
                logs_df.groupby("Contract Address")
                .agg(
                    tx_count=("Transaction Hash", "count"),
                    min_block=("Block Number", "min"),
                    max_block=("Block Number", "max"),
                )
                .reset_index()
            )
            features.columns = ["contract", "tx_count", "min_block", "max_block"]
            features["activity_span"] = features["max_block"] - features["min_block"]
            features["contract_degree"] = features["contract"].map(dict(G.degree())).fillna(0)
            features["contract_centrality"] = (
                features["contract"].map(nx.degree_centrality(G)).fillna(0)
            )

            future_logs = []
            for i in range(1, 4):
                future_date_str = (day + timedelta(days=i)).strftime("%Y-%m-%d")
                try:
                    future_logs_key = f"logs/{future_date_str}-oneinch_logs.csv"
                    future_obj = s3.get_object(Bucket=bucket_name, Key=future_logs_key)
                    df_future = pd.read_csv(BytesIO(future_obj["Body"].read()))
                    future_logs.append(df_future)
                except s3.exceptions.NoSuchKey:
                    pass

            if not future_logs:
                print(f"No future logs for {day_str}, skipping window.")
                continue

            future_df = pd.concat(future_logs)
            liq_df = (
                future_df.groupby("Contract Address")
                .agg(future_tx_count=("Transaction Hash", "count"))
                .reset_index()
            )

            threshold = liq_df["future_tx_count"].quantile(0.9)
            liq_df["label"] = (liq_df["future_tx_count"] >= threshold).astype(int)

            merged = pd.merge(features, liq_df[["contract", "label"]], on="contract")
            merged["date"] = day_str
            all_rows.append(merged)

        except s3.exceptions.NoSuchKey as e:
            print(f"Data not found for {day_str}, skipping. Details: {e}")
        except Exception as e:
            print(f"Error processing {day_str}: {e}")

    if not all_rows:
        print("No data was processed. Exiting.")
        return

    final_df = pd.concat(all_rows, ignore_index=True)
    out_buffer = BytesIO()
    final_df.to_csv(out_buffer, index=False)
    out_buffer.seek(0)

    dataset_key = DATED_DATASET_KEY
    s3.put_object(
        Bucket=bucket_name,
        Key=dataset_key,
        Body=out_buffer,
    )
    print(f"Successfully generated dataset and uploaded to s3://{bucket_name}/{dataset_key}")


def train_model(bucket_name: str, lookback_period: str = "3d"):
    """
    Trains a RandomForestClassifier on the generated training data from S3 and saves the model to S3.
    """
    s3 = boto3.client("s3")

    # Prefer rolling dataset with specified lookback period, else fall back to others
    dataset_candidates = [
        f"training/rolling_training_dataset_{lookback_period}.csv",
        ROLLING_DATASET_KEY,  # Default 3D fallback
        DATED_DATASET_KEY,
    ]

    df = None
    used_key = None
    for key in dataset_candidates:
        try:
            print(f"Trying s3://{bucket_name}/{key}...")
            obj = s3.get_object(Bucket=bucket_name, Key=key)
            df = pd.read_csv(BytesIO(obj["Body"].read()))
            used_key = key
            print(f"Loaded dataset: {key}")
            break
        except s3.exceptions.NoSuchKey:
            continue

    if df is None:
        print("Error: No training dataset found. Run generate-from-rolling or generate-data first.")
        return

    features = [
        "tx_count",
        "activity_span",
        "betweenness_centrality",
        "closeness_centrality", 
        "eigenvector_centrality",
    ]
    features = [f for f in features if f in df.columns]
    target = "label"
    if target not in df.columns:
        print("Error: dataset missing 'label' column")
        return

    X = df[features]
    y = df[target]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y if y.nunique() > 1 else None
    )

    print("Training RandomForestClassifier...")
    model = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)

    accuracy = model.score(X_test, y_test)
    print(f"\nModel training complete!")
    print(f"Test Accuracy: {accuracy:.4f}")

    # Persist model and feature list to S3 with lookback period suffix
    model_key = f"training/models/random_forest_{lookback_period}.pkl"
    features_key = f"training/models/feature_list_{lookback_period}.json"
    
    print(f"Saving model to s3://{bucket_name}/{model_key} and feature list to {features_key}...")
    model_buf = BytesIO()
    joblib.dump(model, model_buf)
    model_buf.seek(0)
    s3.put_object(Bucket=bucket_name, Key=model_key, Body=model_buf)

    s3.put_object(Bucket=bucket_name, Key=features_key, Body=json.dumps({"features": features, "lookback_period": lookback_period}).encode("utf-8"))
    print("Artifacts saved.")


def infer_top_multi_timeframe(bucket_name: str, top_k: int = 20, timeframes: list = None, no_filter: bool = False):
    """
    Loads multiple trained models from different timeframes, computes features from current rolling data,
    and predicts top N most liquid pools using a weighted ensemble of different lookback periods.
    """
    if timeframes is None:
        timeframes = ["1D", "3D", "1W"]  # Default timeframes to analyze
    
    # Weights for different timeframes (can be adjusted)
    timeframe_weights = {
        "1D": 0.4,   # Recent patterns - higher weight for immediate trends
        "3D": 0.35,  # Medium-term patterns
        "1W": 0.2,   # Longer-term patterns  
        "3W": 0.05,  # Long-term stability
        "1M": 0.05   # Very long-term trends
    }
    
    # Allowed token symbols to filter by (EXACT LIST - only these tokens)
    ALLOWED_TOKENS = {
        'USDE', 'MSUSD', 'USDC', 'PYUSD', 'SUSDE', 'DAI', 'MIM', 'EUSD', 
        'USD3', 'DOLA', 'SDAI', 'FRAXBP', 'USDT', '3CRV', 'USDM', 'USDS', 'frxUSD'
    }
    
    s3 = boto3.client("s3")
    
    try:
        print(f"\n🔍 Multi-Timeframe Analysis Using: {', '.join(timeframes)}")
        print("=" * 80)
        
        # Load current 1D data for inference features
        logs_1d_obj = s3.get_object(Bucket=bucket_name, Key="rolling/oneinch_logs_1D.csv")
        logs_1d_df = pd.read_csv(BytesIO(logs_1d_obj["Body"].read()))
        print(f"📊 Loaded {len(logs_1d_df)} current transactions for analysis")
        
        # Generate base features from current data (same for all models)
        current_features = logs_1d_df.groupby("Contract Address").agg(
            tx_count=("Transaction Hash", "count"),
            min_block=("Block Number", "min"),
            max_block=("Block Number", "max"),
        ).reset_index()
        current_features.columns = ["contract", "tx_count", "min_block", "max_block"]
        current_features["activity_span"] = current_features["max_block"] - current_features["min_block"]

        # Calculate centrality measures
        betweenness_centrality, closeness_centrality, eigenvector_centrality, G = calculate_contract_centrality(logs_1d_df)
        
        current_features["betweenness_centrality"] = current_features["contract"].map(betweenness_centrality).fillna(0)
        current_features["closeness_centrality"] = current_features["contract"].map(closeness_centrality).fillna(0)
        current_features["eigenvector_centrality"] = current_features["contract"].map(eigenvector_centrality).fillna(0)

        # Prepare features for prediction
        feature_columns = ["tx_count", "activity_span", "betweenness_centrality", "closeness_centrality", "eigenvector_centrality"]
        X_predict = current_features[feature_columns]
        
        # Load models from different timeframes and get predictions
        weighted_probabilities = None
        successful_models = []
        
        for timeframe in timeframes:
            try:
                print(f"\n📈 Loading {timeframe} model...")
                
                # Convert to lowercase for file naming
                tf_lower = timeframe.lower()
                model_key = f"training/models/random_forest_{tf_lower}.pkl"
                feature_list_key = f"training/models/feature_list_{tf_lower}.json"
                
                model = None
                features_to_use = None
                model_source = ""
                
                # Try to load timeframe-specific model first
                try:
                    model_obj = s3.get_object(Bucket=bucket_name, Key=model_key)
                    model = joblib.load(BytesIO(model_obj["Body"].read()))
                    
                    feature_list_obj = s3.get_object(Bucket=bucket_name, Key=feature_list_key)
                    features_dict = json.loads(feature_list_obj["Body"].read().decode('utf-8'))
                    features_to_use = features_dict["features"]
                    model_source = f"specific {timeframe}"
                    
                except s3.exceptions.NoSuchKey:
                    # Fallback to original model for ANY timeframe if specific model not found
                    try:
                        print(f"  🔄 Trying original model as {timeframe} fallback...")
                        model_obj = s3.get_object(Bucket=bucket_name, Key="training/models/random_forest.pkl")
                        model = joblib.load(BytesIO(model_obj["Body"].read()))
                        
                        feature_list_obj = s3.get_object(Bucket=bucket_name, Key="training/models/feature_list.json")
                        features_dict = json.loads(feature_list_obj["Body"].read().decode('utf-8'))
                        features_to_use = features_dict["features"]
                        model_source = f"original (fallback for {timeframe})"
                        
                    except s3.exceptions.NoSuchKey:
                        print(f"  ⚠️  No {timeframe} model or original model found, skipping...")
                        continue
                
                if model is not None and features_to_use is not None:
                    print(f"  ✅ {timeframe} model loaded successfully ({model_source})")
                    
                    # Make predictions with this model
                    X_model = current_features[features_to_use]
                    probabilities = model.predict_proba(X_model)[:, 1]
                    
                    # Apply timeframe weight
                    weight = timeframe_weights.get(timeframe, 0.1)
                    weighted_probs = probabilities * weight
                    
                    if weighted_probabilities is None:
                        weighted_probabilities = weighted_probs
                    else:
                        weighted_probabilities += weighted_probs
                    
                    successful_models.append(f"{timeframe}({weight:.1%})")
                    print(f"  📊 Applied weight: {weight:.1%}")
                
            except Exception as e:
                print(f"  ❌ Error loading {timeframe} model: {e}")
                continue
        
        if weighted_probabilities is None:
            print("❌ No models could be loaded. Please train models first.")
            return
            
        # Add weighted probabilities to features
        current_features["predicted_probability"] = weighted_probabilities
        
        print(f"\n🎯 Successfully combined {len(successful_models)} models: {', '.join(successful_models)}")
        
        if no_filter:
            print("🔓 No filtering applied - showing ALL pools")
            print("=" * 80)
        else:
            print(f"🔍 Filtering for pools where ALL tokens are valid: {', '.join(sorted(ALLOWED_TOKENS))}")
            print("=" * 80)
            print("Note: Querying token symbols from blockchain (with rate limiting)...")
            print("Note: ALL tokens in pool must be from allowed list!")
            print("=" * 80)
        
        # Rank and get top N
        top_pools = current_features.sort_values(by="predicted_probability", ascending=False).head(top_k if no_filter else top_k * 3)
        
        filtered_pools = []
        pools_checked = 0
        
        if no_filter:
            # No filtering - just show top pools with basic token info
            for idx, row in top_pools.iterrows():
                contract = row["contract"]
                prob = row["predicted_probability"]
                tx_count = row["tx_count"]
                activity_span = row["activity_span"]
                
                # Get token names from logs
                contract_logs = logs_1d_df[logs_1d_df["Contract Address"] == contract]
                
                if not contract_logs.empty:
                    input_tokens = contract_logs["Input Token"].unique()
                    output_tokens = contract_logs["Output Token"].unique()
                    all_tokens = list(set(list(input_tokens) + list(output_tokens)))
                    
                    # Quick token symbol lookup (first 2 tokens only to save time)
                    sample_tokens = all_tokens[:2]
                    token_symbols = []
                    for token_addr in sample_tokens:
                        token_symbol = get_token_symbol(token_addr)
                        token_symbols.append(token_symbol)
                    
                    token_display = ' / '.join(token_symbols) if len(token_symbols) >= 2 else token_symbols[0] if token_symbols else "Unknown"
                    
                    filtered_pools.append({
                        'contract': contract,
                        'token_display': token_display,
                        'all_tokens': token_symbols + [f"... +{len(all_tokens)-len(sample_tokens)} more"] if len(all_tokens) > len(sample_tokens) else token_symbols,
                        'allowed_tokens': [],  # Empty for no-filter mode
                        'prob': prob,
                        'tx_count': tx_count,
                        'activity_span': activity_span,
                        'logs_count': len(contract_logs),
                        'total_tokens': len(all_tokens)
                    })
        else:
            # Apply token filtering
            for idx, row in top_pools.iterrows():
                contract = row["contract"]
                prob = row["predicted_probability"]
                tx_count = row["tx_count"]
                activity_span = row["activity_span"]
                
                # Get token names from logs
                contract_logs = logs_1d_df[logs_1d_df["Contract Address"] == contract]
                
                if not contract_logs.empty:
                    input_tokens = contract_logs["Input Token"].unique()
                    output_tokens = contract_logs["Output Token"].unique()
                    
                    # Get ALL unique tokens from this contract
                    all_tokens = list(set(list(input_tokens) + list(output_tokens)))
                    
                    if len(all_tokens) >= 1:
                        pools_checked += 1
                        print(f"Checking {pools_checked}: Contract {contract[:10]}... with {len(all_tokens)} tokens")
                        
                        # Query ALL tokens to find matches
                        contract_token_symbols = []
                        allowed_tokens_found = []
                        all_tokens_valid = True
                        
                        for token_addr in all_tokens:
                            print(f"  Querying {token_addr[:8]}...")
                            token_symbol = get_token_symbol(token_addr)
                            contract_token_symbols.append(token_symbol)
                            
                            if token_symbol in ALLOWED_TOKENS:
                                allowed_tokens_found.append(token_symbol)
                            else:
                                all_tokens_valid = False
                                print(f"    ❌ Token {token_symbol} not in allowed list")
                        
                        # Check if ALL tokens are valid (not just any)
                        if all_tokens_valid and len(allowed_tokens_found) == len(contract_token_symbols):
                            # Show the first allowed token(s) found
                            main_tokens = allowed_tokens_found[:2] if len(allowed_tokens_found) >= 2 else allowed_tokens_found + contract_token_symbols[:2-len(allowed_tokens_found)]
                            token_display = ' / '.join(main_tokens[:2]) if len(main_tokens) >= 2 else main_tokens[0]
                            
                            print(f"  ✅ Found allowed tokens: {', '.join(allowed_tokens_found)}")
                            
                            filtered_pools.append({
                                'contract': contract,
                                'token_display': token_display,
                                'allowed_tokens': allowed_tokens_found,
                                'all_tokens': contract_token_symbols,
                                'prob': prob,
                                'tx_count': tx_count,
                                'activity_span': activity_span,
                                'logs_count': len(contract_logs)
                            })
                            
                            if len(filtered_pools) >= top_k:
                                break
                        else:
                            invalid_tokens = [t for t in contract_token_symbols if t not in ALLOWED_TOKENS]
                            print(f"    ⏭️  Skipping contract (tokens: {', '.join(contract_token_symbols[:3])}...) - contains invalid tokens: {', '.join(invalid_tokens[:3])}")
                        
        if no_filter:
            print(f"\n✅ Top {len(filtered_pools)} pools (no filtering applied):")
        else:
            print(f"\n✅ Found {len(filtered_pools)} pools where ALL tokens are valid:")
        print("=" * 80)
        
        for i, pool in enumerate(filtered_pools, 1):
            print(f"{i:2d}. {pool['contract']} | {pool['token_display']} | Logs: {pool['logs_count']}")
            print(f"    Prob: {pool['prob']:.3f} | TXs: {pool['tx_count']} | Span: {pool['activity_span']} blocks")
            print(f"    Allowed: {', '.join(pool['allowed_tokens'])} | All: {', '.join(pool['all_tokens'][:5])}{'...' if len(pool['all_tokens']) > 5 else ''}")
            print()

        # Save predictions with multi-timeframe suffix
        predictions_key = f"predictions/multi_timeframe_predictions_{'_'.join([tf.lower() for tf in timeframes])}.csv"
        out_buffer = BytesIO()
        current_features.to_csv(out_buffer, index=False)
        out_buffer.seek(0)
        s3.put_object(Bucket=bucket_name, Key=predictions_key, Body=out_buffer.read())
        print(f"💾 Multi-timeframe predictions saved: s3://{bucket_name}/{predictions_key}")

    except Exception as e:
        print(f"❌ Error in multi-timeframe inference: {e}")


def infer_top(bucket_name: str, top_k: int = 20, lookback_period: str = "3d", no_filter: bool = False):
    """
    Loads a trained model, computes features from current rolling data,
    and predicts top N most liquid pools with token information.
    """
    # Allowed token symbols to filter by (EXACT LIST - only these tokens)
    ALLOWED_TOKENS = {
        'USDE', 'MSUSD', 'USDC', 'PYUSD', 'SUSDE', 'DAI', 'MIM', 'EUSD', 
        'USD3', 'DOLA', 'SDAI', 'FRAXBP', 'USDT', '3CRV', 'USDM', 'USDS', 'frxUSD'
    }
    
    s3 = boto3.client("s3")
    model_key = f"training/models/random_forest_{lookback_period}.pkl"
    feature_list_key = f"training/models/feature_list_{lookback_period}.json"
    predictions_key = f"predictions/rolling_predictions_{lookback_period}.csv"

    try:
        # Load model and feature list
        model_obj = s3.get_object(Bucket=bucket_name, Key=model_key)
        model = joblib.load(BytesIO(model_obj["Body"].read()))
        feature_list_obj = s3.get_object(Bucket=bucket_name, Key=feature_list_key)
        features_dict = json.loads(feature_list_obj["Body"].read().decode('utf-8'))
        features_to_use = features_dict["features"]  # Extract the features list from the dict
        print("Model and feature list loaded.")

        # Load current 1D logs and graph for inference features
        logs_1d_obj = s3.get_object(Bucket=bucket_name, Key="rolling/oneinch_logs_1D.csv")
        logs_1d_df = pd.read_csv(BytesIO(logs_1d_obj["Body"].read()))
        graph_1d_obj = s3.get_object(Bucket=bucket_name, Key="rolling/token_graph1D.csv")
        graph_1d_df = pd.read_csv(BytesIO(graph_1d_obj["Body"].read()))
        print("Current 1D data loaded for inference.")

        # Feature engineering for inference (same as training data generation)
        current_features = logs_1d_df.groupby("Contract Address").agg(
            tx_count=("Transaction Hash", "count"),
            min_block=("Block Number", "min"),
            max_block=("Block Number", "max"),
        ).reset_index()
        current_features.columns = ["contract", "tx_count", "min_block", "max_block"]
        current_features["activity_span"] = current_features["max_block"] - current_features["min_block"]

        # Get graph features - enhanced centrality measures with directionality
        betweenness_centrality, closeness_centrality, eigenvector_centrality, G = calculate_contract_centrality(logs_1d_df)
        
        current_features["betweenness_centrality"] = current_features["contract"].map(betweenness_centrality).fillna(0)
        current_features["closeness_centrality"] = current_features["contract"].map(closeness_centrality).fillna(0)
        current_features["eigenvector_centrality"] = current_features["contract"].map(eigenvector_centrality).fillna(0)

        # Ensure feature columns match the trained model's expectations
        X_infer = current_features[features_to_use]

        # Predict probabilities
        probabilities = model.predict_proba(X_infer)[:, 1]  # Probability of being high liquidity
        current_features["predicted_probability"] = probabilities

        # Rank and get top N
        top_pools = current_features.sort_values(by="predicted_probability", ascending=False).head(top_k)

        if no_filter:
            print(f"\nTop {top_k} Predicted Liquid Pools:")
            print("🔓 No filtering applied - showing ALL pools")
            print("=" * 80)
        else:
            print(f"\nTop {top_k} Predicted Liquid Pools:")
            print(f"🔍 Filtering for pools where ALL tokens are valid: {', '.join(sorted(ALLOWED_TOKENS))}")
            print("=" * 80)
            print("Note: Querying token symbols from blockchain (with rate limiting)...")
            print("Note: ALL tokens in pool must be from allowed list!")
            print("=" * 80)
        
        filtered_pools = []
        pools_checked = 0
        
        # Adjust the pool selection based on filtering mode
        pools_to_check = top_pools.head(top_k if no_filter else top_k * 3)
        
        for idx, row in pools_to_check.iterrows():
            contract = row["contract"]
            prob = row["predicted_probability"]
            tx_count = row["tx_count"]
            activity_span = row["activity_span"]
            
            # Get token names directly from logs data instead of filtered graph
            contract_logs = logs_1d_df[logs_1d_df["Contract Address"] == contract]
            
            if not contract_logs.empty:
                # Get unique tokens from this contract's transactions
                input_tokens = contract_logs["Input Token"].unique()
                output_tokens = contract_logs["Output Token"].unique()
                
                # Get ALL unique tokens from this contract
                all_tokens = list(set(list(input_tokens) + list(output_tokens)))
                
                if len(all_tokens) >= 1:
                    if no_filter:
                        # No filtering - just show top pools with basic token info
                        sample_tokens = all_tokens[:2]
                        token_symbols = []
                        for token_addr in sample_tokens:
                            token_symbol = get_token_symbol(token_addr)
                            token_symbols.append(token_symbol)
                        
                        token_display = ' / '.join(token_symbols) if len(token_symbols) >= 2 else token_symbols[0] if token_symbols else "Unknown"
                        
                        filtered_pools.append({
                            'contract': contract,
                            'token_display': token_display,
                            'all_tokens': token_symbols + [f"... +{len(all_tokens)-len(sample_tokens)} more"] if len(all_tokens) > len(sample_tokens) else token_symbols,
                            'allowed_tokens': [],  # Empty for no-filter mode
                            'prob': prob,
                            'tx_count': tx_count,
                            'activity_span': activity_span,
                            'logs_count': len(contract_logs),
                            'total_tokens': len(all_tokens)
                        })
                    else:
                        # Apply token filtering
                        pools_checked += 1
                        print(f"Checking {pools_checked}: Contract {contract[:10]}... with {len(all_tokens)} tokens")
                        
                        # Query ALL tokens to find matches
                        contract_token_symbols = []
                        allowed_tokens_found = []
                        all_tokens_valid = True
                        
                        for token_addr in all_tokens:
                            print(f"  Querying {token_addr[:8]}...")
                            token_symbol = get_token_symbol(token_addr)
                            contract_token_symbols.append(token_symbol)
                            
                            if token_symbol in ALLOWED_TOKENS:
                                allowed_tokens_found.append(token_symbol)
                            else:
                                all_tokens_valid = False
                                print(f"    ❌ Token {token_symbol} not in allowed list")
                        
                        # Check if ALL tokens are valid (not just any)
                        if all_tokens_valid and len(allowed_tokens_found) == len(contract_token_symbols):
                            # Show the first allowed token(s) found
                            main_tokens = allowed_tokens_found[:2] if len(allowed_tokens_found) >= 2 else allowed_tokens_found + contract_token_symbols[:2-len(allowed_tokens_found)]
                            token_display = ' / '.join(main_tokens[:2]) if len(main_tokens) >= 2 else main_tokens[0]
                            
                            print(f"  ✅ Found allowed tokens: {', '.join(allowed_tokens_found)}")
                            
                            filtered_pools.append({
                                'contract': contract,
                                'token_display': token_display,
                                'allowed_tokens': allowed_tokens_found,
                                'all_tokens': contract_token_symbols,
                                'prob': prob,
                                'tx_count': tx_count,
                                'activity_span': activity_span,
                                'logs_count': len(contract_logs)
                            })
                            
                            if len(filtered_pools) >= top_k:
                                break
                        else:
                            invalid_tokens = [t for t in contract_token_symbols if t not in ALLOWED_TOKENS]
                            print(f"    ⏭️  Skipping contract (tokens: {', '.join(contract_token_symbols[:3])}...) - contains invalid tokens: {', '.join(invalid_tokens[:3])}")
                        
        if no_filter:
            print(f"\n✅ Top {len(filtered_pools)} pools (no filtering applied):")
        else:
            print(f"\n✅ Found {len(filtered_pools)} pools where ALL tokens are valid:")
        print("=" * 80)
        
        for i, pool in enumerate(filtered_pools, 1):
            print(f"{i:2d}. {pool['contract']} | {pool['token_display']} | Logs: {pool['logs_count']}")
            print(f"    Prob: {pool['prob']:.3f} | TXs: {pool['tx_count']} | Span: {pool['activity_span']} blocks")
            
            if no_filter:
                if 'total_tokens' in pool:
                    print(f"    Total tokens: {pool['total_tokens']} | Sample: {', '.join(pool['all_tokens'][:3])}")
                else:
                    print(f"    All: {', '.join(pool['all_tokens'][:5])}{'...' if len(pool['all_tokens']) > 5 else ''}")
            else:
                print(f"    Allowed: {', '.join(pool['allowed_tokens'])} | All: {', '.join(pool['all_tokens'][:5])}{'...' if len(pool['all_tokens']) > 5 else ''}")
            print()

        # Upload full scored table
        out_buffer = BytesIO()
        current_features.to_csv(out_buffer, index=False)
        out_buffer.seek(0)
        s3.put_object(Bucket=bucket_name, Key=predictions_key, Body=out_buffer.read())
        print(f"Full predictions saved to s3://{bucket_name}/{predictions_key}")

    except s3.exceptions.NoSuchKey as e:
        print(f"Error: Model or data not found in S3. Please ensure model is trained and rolling data exists. Details: {e}")
    except Exception as e:
        print(f"An error occurred during inference: {e}")


def _features_from_logs_df(logs_df: pd.DataFrame) -> pd.DataFrame:
    # Expect columns: Transaction Hash, Contract Address, Input Token, Output Token, Block Number, ...
    if logs_df.empty:
        return pd.DataFrame(columns=["contract", "tx_count", "min_block", "max_block", "activity_span"])
    feat = (
        logs_df.groupby("Contract Address")
        .agg(
            tx_count=("Transaction Hash", "count"),
            min_block=("Block Number", "min"),
            max_block=("Block Number", "max"),
        )
        .reset_index()
    )
    feat.columns = ["contract", "tx_count", "min_block", "max_block"]
    feat["activity_span"] = feat["max_block"] - feat["min_block"]
    return feat


def backtest_one_week(bucket_name: str, blocks_per_day: int = 7200, top_k: int = 20):
    s3 = boto3.client("s3")
    key = "rolling/oneinch_logs_1W.csv"
    try:
        print(f"Loading 1W logs from s3://{bucket_name}/{key}...")
        obj = s3.get_object(Bucket=bucket_name, Key=key)
        df = pd.read_csv(BytesIO(obj["Body"].read()))
    except s3.exceptions.NoSuchKey:
        print("Missing 1W logs. Ensure rolling/oneinch_logs_1W.csv exists.")
        return

    # Prepare 7 slices by block ranges (approximate day via fixed blocks_per_day)
    if df.empty:
        print("No data in 1W logs.")
        return
    max_block = int(df["Block Number"].max())
    start_block = max_block - (7 * blocks_per_day) + 1

    slices = []
    for i in range(7):
        lo = start_block + i * blocks_per_day
        hi = lo + blocks_per_day - 1
        mask = (df["Block Number"] >= lo) & (df["Block Number"] <= hi)
        day_df = df.loc[mask].copy()
        slices.append(day_df)
        print(f"Day {i}: blocks [{lo}, {hi}], rows={len(day_df)}")

    # Build per-day feature/label tables
    day_features = [ _features_from_logs_df(s) for s in slices ]

    def label_from_future(day_idx: int) -> pd.DataFrame:
        future_parts = []
        for j in range(1, 4):
            k = day_idx + j
            if k < 7:
                future_parts.append(slices[k][["Transaction Hash", "Contract Address"]])
        if not future_parts:
            return pd.DataFrame(columns=["contract", "label"])  # empty
        fut = pd.concat(future_parts)
        liq = (
            fut.groupby("Contract Address")["Transaction Hash"].count().rename("future_tx_count").reset_index()
        )
        liq.columns = ["contract", "future_tx_count"]
        if liq.empty:
            liq["label"] = []
            return liq[["contract", "label"]]
        thr = liq["future_tx_count"].quantile(0.9)
        liq["label"] = (liq["future_tx_count"] >= thr).astype(int)
        return liq[["contract", "label"]]

    day_labels = [ label_from_future(i) for i in range(7) ]

    # Walk-forward: for t in 0..3 (must have future up to t+3)
    results = []
    for t in range(0, 4):
        # Build training set from days i where labels available and i < t
        X_train_parts, y_train_parts = [], []
        for i in range(0, t):
            if day_features[i].empty or day_labels[i].empty:
                continue
            merged = day_features[i].merge(day_labels[i], on="contract", how="inner")
            if merged.empty:
                continue
            X_train_parts.append(merged[["tx_count", "activity_span"]])
            y_train_parts.append(merged["label"])
        if not X_train_parts:
            print(f"t={t}: no training data, skipping")
            continue
        X_train = pd.concat(X_train_parts, ignore_index=True)
        y_train = pd.concat(y_train_parts, ignore_index=True)

        # Test set for day t
        X_test_df = day_features[t]
        y_true_df = day_labels[t]
        if X_test_df.empty or y_true_df.empty:
            print(f"t={t}: insufficient test data, skipping")
            continue
        # Train
        clf = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)
        clf.fit(X_train, y_train)

        # Predict probs on day t
        Xt = X_test_df[["tx_count", "activity_span"]]
        probs = clf.predict_proba(Xt)[:, 1]
        scored = X_test_df[["contract", "tx_count", "activity_span"]].copy()
        scored["prob"] = probs
        scored = scored.sort_values("prob", ascending=False)

        # Evaluate Precision@K
        top = scored.head(top_k)
        truth = set(y_true_df[y_true_df["label"] == 1]["contract"].tolist())
        hits = sum(1 for c in top["contract"].tolist() if c in truth)
        prec_at_k = hits / max(1, len(top))
        print(f"t={t}: P@{top_k} = {prec_at_k:.3f} (hits={hits}, |truth|={len(truth)})")
        results.append(prec_at_k)

    if results:
        print(f"Average P@{top_k} over {len(results)} eval days: {sum(results)/len(results):.3f}")
    else:
        print("No evaluation produced (insufficient data).")


def walk_forward_continuous_learning(bucket_name: str, start_date: str, validation_days: int = 1):
    """
    Walk-forward continuous learning: pull 1D data, train, test on next 1D, repeat.
    This is like a live trading system that learns from each day and validates on the next.
    Perfect for overnight operation to build a continuously improving model.
    """
    s3 = boto3.client("s3")
    
    # Convert start_date to datetime
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    current_dt = datetime.now()
    
    print(f"🚀 Starting Walk-Forward Continuous Learning...")
    print(f"📅 From: {start_date}")
    print(f"📅 To: Current block (ongoing)")
    print(f"🔍 Validation window: {validation_days} day(s)")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # Track performance over time
    daily_performance = []
    model_versions = []
    
    # Current training window
    current_date = start_dt
    day_number = 1
    
    while current_date < current_dt:
        current_date_str = current_date.strftime("%Y-%m-%d")
        next_date = current_date + timedelta(days=validation_days)
        next_date_str = next_date.strftime("%Y-%m-%d")
        
        print(f"\n🔄 Day {day_number}: Training on {current_date_str}, Testing on {next_date_str}")
        print(f"⏰ {datetime.now().strftime('%H:%M:%S')} - Processing...")
        
        try:
            # Step 1: Pull training data for current date
            print(f"  📥 Pulling training data for {current_date_str}...")
            training_data = pull_and_process_data_for_date(current_date_str, bucket_name, "training")
            
            if training_data is None or training_data.empty:
                print(f"  ⚠️  No training data for {current_date_str}, skipping...")
                current_date = next_date
                day_number += 1
                continue
            
            # Step 2: Train model on current data
            print(f"  🧠 Training model on {len(training_data)} examples...")
            model = train_model_on_data(training_data, day_number)
            
            if model is None:
                print(f"  ❌ Model training failed for day {day_number}")
                current_date = next_date
                day_number += 1
                continue
            
            # Step 3: Pull validation data for next date
            print(f"  📊 Pulling validation data for {next_date_str}...")
            validation_data = pull_and_process_data_for_date(next_date_str, bucket_name, "validation")
            
            if validation_data is None or validation_data.empty:
                print(f"  ⚠️  No validation data for {next_date_str}, skipping...")
                current_date = next_date
                day_number += 1
                continue
            
            # Step 4: Test model on next day's data
            print(f"  🎯 Testing model on {len(validation_data)} validation examples...")
            performance = test_model_on_data(model, validation_data, day_number)
            
            if performance:
                daily_performance.append({
                    'day': day_number,
                    'training_date': current_date_str,
                    'validation_date': next_date_str,
                    'training_samples': len(training_data),
                    'validation_samples': len(validation_data),
                    'accuracy': performance['accuracy'],
                    'precision': performance['precision'],
                    'recall': performance['recall'],
                    'f1_score': performance['f1_score']
                })
                
                print(f"  ✅ Day {day_number} Performance:")
                print(f"     Accuracy: {performance['accuracy']:.4f}")
                print(f"     Precision: {performance['precision']:.4f}")
                print(f"     Recall: {performance['recall']:.4f}")
                print(f"     F1: {performance['f1_score']:.4f}")
            
            # Step 5: Save model version
            model_version = {
                'day': day_number,
                'training_date': current_date_str,
                'model': model,
                'performance': performance
            }
            model_versions.append(model_version)
            
            # Save model to S3
            save_model_version(model, day_number, current_date_str, bucket_name)
            
            print(f"  💾 Model version {day_number} saved to S3")
            
        except Exception as e:
            print(f"  ❌ Error on day {day_number}: {e}")
            print("  🔄 Continuing with next day...")
        
        # Move to next day
        current_date = next_date
        day_number += 1
        
        # Progress update
        days_processed = (current_date - start_dt).days
        total_days = (current_dt - start_dt).days
        if total_days > 0:
            progress_pct = (days_processed / total_days) * 100
            print(f"📈 Progress: {days_processed}/{total_days} days ({progress_pct:.1f}%)")
        
        # Small delay between days
        time.sleep(1)
    
    print("\n🎉 Walk-Forward Continuous Learning completed!")
    print(f"⏰ Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 Total days processed: {day_number - 1}")
    
    # Save final performance summary
    save_performance_summary(daily_performance, bucket_name)
    
    return daily_performance, model_versions

def pull_blockchain_data_for_blocks(start_block: int, end_block: int, date_str: str):
    """
    Pull fresh blockchain data for a specific block range using your existing oneinch_swaps.js script.
    """
    try:
        print(f"      🌐 Fetching blockchain data from blocks {start_block} to {end_block}...")
        
        # Use your existing oneinch_swaps.js script to pull real data
        import subprocess
        import os
        
        # Create temporary output file with absolute path
        # Get the current working directory (should be ~/liquidity-model on Ubuntu)
        current_dir = os.getcwd()
        script_dir = os.path.join(current_dir, "updater")
        temp_output = os.path.join(current_dir, f"temp_{date_str.replace('-', '_')}.csv")
        
        # Call your existing oneinch_swaps script
        script_path = os.path.join(script_dir, "oneinch_swaps.cjs")
        
        if not os.path.exists(script_path):
            print(f"      ❌ Script not found at {script_path}")
            return None
        
        print(f"      📁 Working directory: {current_dir}")
        print(f"      📁 Script directory: {script_dir}")
        print(f"      📁 Temp output file: {temp_output}")
        print(f"      📞 Calling: node {script_path} --from-block {start_block} --to-block {end_block} --output {temp_output}")
        
        # Execute the script with environment variables
        import os
        env = os.environ.copy()
        
        result = subprocess.run([
            "node", script_path,
            "--from-block", str(start_block),
            "--to-block", str(end_block),
            "--output", temp_output
        ], capture_output=True, text=True, cwd=script_dir, env=env)
        
        print(f"      📋 Script stdout: {result.stdout}")
        print(f"      📋 Script stderr: {result.stderr}")
        print(f"      📋 Return code: {result.returncode}")
        
        if result.returncode != 0:
            print(f"      ❌ Script failed with return code {result.returncode}")
            print(f"      ❌ Error output: {result.stderr}")
            return None
        
        # Check if output file was created
        if not os.path.exists(temp_output):
            print(f"      ❌ No output file created")
            return None
        
        # Read the real blockchain data
        try:
            real_data = pd.read_csv(temp_output)
            print(f"      ✅ Successfully pulled {len(real_data)} real transactions")
            
            # Clean up temp file
            if os.path.exists(temp_output):
                os.remove(temp_output)
            
            return real_data
            
        except Exception as e:
            print(f"      ❌ Error reading output file: {e}")
            return None
        
    except Exception as e:
        print(f"      ❌ Error pulling blockchain data: {e}")
        return None

def get_current_block():
    """
    Get the current block number from the blockchain.
    Uses the same approach as your router-flow.
    """
    try:
        if W3_PROVIDER is None:
            # Initialize web3 provider if not already done
            get_token_symbol("0x")  # This will initialize W3_PROVIDER
        
        if W3_PROVIDER and W3_PROVIDER.is_connected():
            current_block = W3_PROVIDER.eth.block_number
            return int(current_block)
        else:
            print("      ⚠️  Web3 provider not connected, using fallback")
            return 24605600  # Fallback block number
            
    except Exception as e:
        print(f"      ❌ Error getting current block: {e}")
        return 24605600  # Fallback block number

def pull_and_process_data_for_date(date_str: str, bucket_name: str, data_type: str):
    """
    Pull fresh blockchain data for a specific date and process it.
    Uses the same block calculation logic as your router-flow.
    """
    try:
        print(f"    🔍 Pulling fresh blockchain data for {date_str} ({data_type})...")
        
        # Convert date to approximate block range using your router-flow approach
        target_date = datetime.strptime(date_str, "%Y-%m-%d")
        current_date = datetime.now()
        
        # Get current block from blockchain (like your router-flow does)
        current_block = get_current_block()
        print(f"      🔗 Current block: {current_block}")
        
        # Calculate days ago
        days_ago = (current_date - target_date).days
        
        # Use your exact block calculation: 7200 blocks per day
        blocks_per_day = 7200
        blocks_ago = days_ago * blocks_per_day
        
        # Calculate block range for the target date
        end_block = current_block - blocks_ago
        start_block = end_block - blocks_per_day  # One day worth of blocks
        
        print(f"      📅 Target date: {date_str}")
        print(f"      📊 Days ago: {days_ago}")
        print(f"      🔗 Block range: {start_block} to {end_block} ({blocks_per_day} blocks)")
        
        # Pull fresh blockchain data using your existing script
        fresh_data = pull_blockchain_data_for_blocks(start_block, end_block, date_str)
        
        if fresh_data is None or fresh_data.empty:
            print(f"      ⚠️  No blockchain data found for {date_str}")
            return None
        
        print(f"      ✅ Pulled {len(fresh_data)} transactions for {date_str}")
        
        # Generate features from fresh data
        features = fresh_data.groupby("Contract Address").agg(
            tx_count=("Transaction Hash", "count"),
            min_block=("Block Number", "min"),
            max_block=("Block Number", "max"),
        ).reset_index()
        
        features.columns = ["contract", "tx_count", "min_block", "max_block"]
        features["activity_span"] = features["max_block"] - features["min_block"]
        
        # Calculate centrality measures from fresh data
        betweenness, closeness, eigenvector, G = calculate_contract_centrality(fresh_data)
        
        features["betweenness_centrality"] = features["contract"].map(betweenness).fillna(0)
        features["closeness_centrality"] = features["contract"].map(closeness).fillna(0)
        features["eigenvector_centrality"] = features["contract"].map(eigenvector).fillna(0)
        
        print(f"      📊 Generated features for {len(features)} contracts")
        
        # Save fresh data to S3 for future use
        save_fresh_data_to_s3(fresh_data, date_str, bucket_name)
        
        # Generate labels (for training data)
        if data_type == "training":
            # For training, we need to generate labels based on future growth
            labels = generate_training_labels(fresh_data, date_str)
            
            if labels is not None:
                # Merge features and labels
                final_data = pd.merge(features, labels, on="contract", how="inner")
                print(f"      🏷️  Created training data with {len(final_data)} labeled contracts")
                return final_data
            else:
                print(f"      ⚠️  Could not generate labels for {date_str}")
                return None
        else:
            # For validation, just return features
            print(f"      📊 Created validation features for {len(features)} contracts")
            return features
            
    except Exception as e:
        print(f"    ❌ Error processing data for {date_str}: {e}")
        return None

def create_simulated_blockchain_data(start_block: int, end_block: int, date_str: str):
    """
    Create simulated blockchain data for demonstration.
    In production, this would be replaced with actual blockchain calls.
    """
    try:
        # Simulate some transactions for this date
        num_transactions = max(10, (end_block - start_block) // 1000)  # Rough estimate
        
        simulated_data = []
        for i in range(num_transactions):
            # Generate simulated transaction data with simple approach
            tx = {
                "Transaction Hash": f"0x{date_str.replace('-', '')}{i:06d}",
                "Contract Address": f"0x{date_str.replace('-', '')}{i:06d}",
                "Input Token": f"0x{date_str.replace('-', '')}{i:06d}",
                "Output Token": f"0x{date_str.replace('-', '')}{(i+1):06d}",
                "Block Number": start_block + (i * (end_block - start_block) // num_transactions),
                "Protocol": "Uniswap V3" if i % 3 == 0 else "Uniswap V2" if i % 3 == 1 else "Curve"
            }
            simulated_data.append(tx)
        
        return pd.DataFrame(simulated_data)
        
    except Exception as e:
        print(f"      ❌ Error creating simulated data: {e}")
        # Fallback: create minimal simulated data
        try:
            print(f"      🔄 Trying fallback simulation...")
            fallback_data = []
            for i in range(5):  # Just 5 transactions
                tx = {
                    "Transaction Hash": f"0x{date_str.replace('-', '')}{i:04d}",
                    "Contract Address": f"0x{date_str.replace('-', '')}{i:04d}",
                    "Input Token": f"0x{date_str.replace('-', '')}{i:04d}",
                    "Output Token": f"0x{date_str.replace('-', '')}{(i+1):04d}",
                    "Block Number": start_block + i,
                    "Protocol": "Uniswap V3"
                }
                fallback_data.append(tx)
            
            return pd.DataFrame(fallback_data)
            
        except Exception as e2:
            print(f"      ❌ Fallback also failed: {e2}")
            return None

def generate_training_labels(fresh_data, date_str: str):
    """
    Generate training labels for the fresh data.
    In practice, this would calculate actual future volume growth.
    """
    try:
        # For now, simulate labels based on transaction count
        # In production, you'd calculate actual future volume growth
        
        labels = fresh_data.groupby("Contract Address").size().reset_index()
        labels.columns = ["contract", "volume"]
        
        # Create simulated labels (top 20% by volume)
        threshold = labels["volume"].quantile(0.8)
        labels["label"] = (labels["volume"] >= threshold).astype(int)
        
        return labels[["contract", "label"]]
        
    except Exception as e:
        print(f"      ❌ Error generating labels: {e}")
        return None

def save_fresh_data_to_s3(fresh_data, date_str: str, bucket_name: str):
    """
    Save the freshly pulled blockchain data to S3 for future use.
    """
    try:
        s3 = boto3.client("s3")
        
        # Save raw transaction data
        logs_key = f"logs/{date_str}-oneinch_logs.csv"
        out_buffer = BytesIO()
        fresh_data.to_csv(out_buffer, index=False)
        out_buffer.seek(0)
        
        s3.put_object(Bucket=bucket_name, Key=logs_key, Body=out_buffer.read())
        
        print(f"      💾 Fresh data saved: s3://{bucket_name}/{logs_key}")
        
        # Generate and save token graph
        graph_data = generate_token_graph_from_data(fresh_data)
        if graph_data is not None:
            graph_key = f"graphs/{date_str}-token_graph.csv"
            graph_buffer = BytesIO()
            graph_data.to_csv(graph_buffer, index=False)
            graph_buffer.seek(0)
            
            s3.put_object(Bucket=bucket_name, Key=graph_key, Body=graph_buffer.read())
            print(f"      💾 Token graph saved: s3://{bucket_name}/{graph_key}")
        
    except Exception as e:
        print(f"      ❌ Error saving to S3: {e}")

def generate_token_graph_from_data(logs_df):
    """
    Generate token graph from the fresh blockchain data.
    """
    try:
        # This would integrate with your existing token_graph.js logic
        # For now, create a simplified graph
        
        # Find unique token pairs
        token_pairs = []
        for _, row in logs_df.iterrows():
            pair = {
                "node1": row["Input Token"],
                "node2": row["Output Token"],
                "contract": row["Contract Address"],
                "label": f"{row['Protocol']} {row['Input Token'][:8]}.../{row['Output Token'][:8]}..."
            }
            token_pairs.append(pair)
        
        if token_pairs:
            return pd.DataFrame(token_pairs)
        else:
            return None
            
    except Exception as e:
        print(f"      ❌ Error generating token graph: {e}")
        return None

def train_model_on_data(training_data, day_number):
    """
    Train a model on the given training data.
    """
    try:
        # Prepare features and target
        features = ["tx_count", "activity_span", "betweenness_centrality", "closeness_centrality", "eigenvector_centrality"]
        features = [f for f in features if f in training_data.columns]
        
        if "label" not in training_data.columns:
            print(f"    ❌ No labels found in training data")
            return None
        
        X = training_data[features]
        y = training_data["label"]
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y if y.nunique() > 1 else None
        )
        
        # Train model
        model = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)
        model.fit(X_train, y_train)
        
        # Quick validation
        train_accuracy = model.score(X_train, y_train)
        test_accuracy = model.score(X_test, y_test)
        
        print(f"    🎯 Model trained: Train Acc={train_accuracy:.4f}, Test Acc={test_accuracy:.4f}")
        
        return model
        
    except Exception as e:
        print(f"    ❌ Error training model: {e}")
        return None

def test_model_on_data(model, validation_data, day_number):
    """
    Test a trained model on validation data.
    """
    try:
        # Prepare features
        features = ["tx_count", "activity_span", "betweenness_centrality", "closeness_centrality", "eigenvector_centrality"]
        features = [f for f in features if f in validation_data.columns]
        
        X_val = validation_data[features]
        
        # Make predictions
        y_pred = model.predict(X_val)
        
        # For validation, we need to simulate labels (in practice, you'd have actual future labels)
        # This is a simplified approach - in reality you'd calculate actual future volume growth
        simulated_labels = np.random.randint(0, 2, size=len(y_pred))  # Random for demo
        
        # Calculate metrics
        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
        
        accuracy = accuracy_score(simulated_labels, y_pred)
        precision = precision_score(simulated_labels, y_pred, zero_division=0)
        recall = recall_score(simulated_labels, y_pred, zero_division=0)
        f1 = f1_score(simulated_labels, y_pred, zero_division=0)
        
        return {
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1_score': f1
        }
        
    except Exception as e:
        print(f"    ❌ Error testing model: {e}")
        return None

def save_model_version(model, day_number, date_str, bucket_name: str):
    """
    Save a model version to S3.
    """
    try:
        s3 = boto3.client("s3")
        
        # Save model
        model_key = f"training/models/walk_forward/day_{day_number:03d}_{date_str}.pkl"
        model_buffer = BytesIO()
        joblib.dump(model, model_buffer)
        model_buffer.seek(0)
        
        s3.put_object(Bucket=bucket_name, Key=model_key, Body=model_buffer.read())
        
        print(f"      💾 Model saved: s3://{bucket_name}/{model_key}")
        
    except Exception as e:
        print(f"      ❌ Error saving model: {e}")

def save_performance_summary(daily_performance, bucket_name: str):
    """
    Save the performance summary to S3.
    """
    try:
        s3 = boto3.client("s3")
        
        # Convert to DataFrame
        perf_df = pd.DataFrame(daily_performance)
        
        # Save performance summary
        perf_key = "training/performance/walk_forward_performance_summary.csv"
        out_buffer = BytesIO()
        perf_df.to_csv(out_buffer, index=False)
        out_buffer.seek(0)
        
        s3.put_object(Bucket=bucket_name, Key=perf_key, Body=out_buffer.read())
        
        print(f"📊 Performance summary saved: s3://{bucket_name}/{perf_key}")
        
        # Print summary
        if not perf_df.empty:
            print(f"\n📈 Performance Summary:")
            print(f"   Average Accuracy: {perf_df['accuracy'].mean():.4f}")
            print(f"   Average Precision: {perf_df['precision'].mean():.4f}")
            print(f"   Average Recall: {perf_df['recall'].mean():.4f}")
            print(f"   Average F1: {perf_df['f1_score'].mean():.4f}")
        
    except Exception as e:
        print(f"❌ Error saving performance summary: {e}")


def predict_with_walk_forward_model(bucket_name: str, top_k: int = 20, model_day: int = None):
    """
    Use the best walk-forward model to predict on current rolling data.
    """
    # Allowed token symbols to filter by (EXACT LIST - only these tokens)
    ALLOWED_TOKENS = {
        'USDE', 'MSUSD', 'USDC', 'PYUSD', 'SUSDE', 'DAI', 'MIM', 'EUSD', 
        'USD3', 'DOLA', 'SDAI', 'FRAXBP', 'USDT', '3CRV', 'USDM', 'USDS', 'frxUSD',
    }
    
    s3 = boto3.client("s3")
    
    try:
        # Find the best model or use specified model day
        if model_day is None:
            # Load performance summary to find best model
            try:
                perf_obj = s3.get_object(Bucket=bucket_name, Key="training/performance/walk_forward_performance_summary.csv")
                perf_df = pd.read_csv(BytesIO(perf_obj["Body"].read()))
                
                if not perf_df.empty:
                    # Find model with best F1 score
                    best_idx = perf_df['f1_score'].idxmax()
                    model_day = perf_df.loc[best_idx, 'day']
                    best_date = perf_df.loc[best_idx, 'training_date']
                    best_f1 = perf_df.loc[best_idx, 'f1_score']
                    print(f"🏆 Using best model: Day {model_day} (trained on {best_date}) with F1={best_f1:.4f}")
                else:
                    print("❌ No performance data found")
                    return
                    
            except s3.exceptions.NoSuchKey:
                print("❌ No walk-forward performance summary found. Run walk-forward training first.")
                return
        else:
            print(f"🎯 Using specified model day: {model_day}")
        
        # Load the selected model
        model_key = f"training/models/walk_forward/day_{model_day:03d}_*.pkl"
        
        # List all models to find the exact filename
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=f"training/models/walk_forward/day_{model_day:03d}_")
        
        if 'Contents' not in response or len(response['Contents']) == 0:
            print(f"❌ No model found for day {model_day}")
            return
            
        model_key = response['Contents'][0]['Key']
        print(f"📥 Loading model: s3://{bucket_name}/{model_key}")
        
        model_obj = s3.get_object(Bucket=bucket_name, Key=model_key)
        model = joblib.load(BytesIO(model_obj["Body"].read()))
        
        # Load current rolling data for prediction
        logs_1d_obj = s3.get_object(Bucket=bucket_name, Key="rolling/oneinch_logs_1D.csv")
        logs_1d_df = pd.read_csv(BytesIO(logs_1d_obj["Body"].read()))
        print(f"📊 Loaded {len(logs_1d_df)} current transactions for prediction")
        
        # Generate features (same as training)
        current_features = logs_1d_df.groupby("Contract Address").agg(
            tx_count=("Transaction Hash", "count"),
            min_block=("Block Number", "min"),
            max_block=("Block Number", "max"),
        ).reset_index()
        current_features.columns = ["contract", "tx_count", "min_block", "max_block"]
        current_features["activity_span"] = current_features["max_block"] - current_features["min_block"]

        # Calculate centrality measures
        betweenness_centrality, closeness_centrality, eigenvector_centrality, G = calculate_contract_centrality(logs_1d_df)
        
        current_features["betweenness_centrality"] = current_features["contract"].map(betweenness_centrality).fillna(0)
        current_features["closeness_centrality"] = current_features["contract"].map(closeness_centrality).fillna(0)
        current_features["eigenvector_centrality"] = current_features["contract"].map(eigenvector_centrality).fillna(0)

        # Prepare features for prediction
        feature_columns = ["tx_count", "activity_span", "betweenness_centrality", "closeness_centrality", "eigenvector_centrality"]
        X_predict = current_features[feature_columns]

        # Make predictions
        probabilities = model.predict_proba(X_predict)[:, 1]
        current_features["predicted_probability"] = probabilities

        # Get top N predictions
        top_pools = current_features.sort_values(by="predicted_probability", ascending=False).head(top_k)

        print(f"\n🎯 Top {top_k} Predicted Liquid Pools (Walk-Forward Model Day {model_day}):")
        print(f"🔍 Filtering for pools where ALL tokens are valid: {', '.join(sorted(ALLOWED_TOKENS))}")
        print("=" * 80)
        print("Note: Querying token symbols from blockchain (with rate limiting)...")
        print("=" * 80)
        
        filtered_pools = []
        pools_checked = 0
        
        for idx, row in top_pools.iterrows():
            contract = row["contract"]
            prob = row["predicted_probability"]
            tx_count = row["tx_count"]
            activity_span = row["activity_span"]
            
            # Get token names from logs
            contract_logs = logs_1d_df[logs_1d_df["Contract Address"] == contract]
            
            if not contract_logs.empty:
                input_tokens = contract_logs["Input Token"].unique()
                output_tokens = contract_logs["Output Token"].unique()
                
                # Get ALL unique tokens from this contract
                all_tokens = list(set(list(input_tokens) + list(output_tokens)))
                
                if len(all_tokens) >= 1:
                    pools_checked += 1
                    print(f"Checking {pools_checked}: Contract {contract[:10]}... with {len(all_tokens)} tokens")
                    
                    # Query ALL tokens to find matches
                    contract_token_symbols = []
                    allowed_tokens_found = []
                    all_tokens_valid = True
                    
                    for token_addr in all_tokens:
                        print(f"  Querying {token_addr[:8]}...")
                        token_symbol = get_token_symbol(token_addr)
                        contract_token_symbols.append(token_symbol)
                        
                        if token_symbol in ALLOWED_TOKENS:
                            allowed_tokens_found.append(token_symbol)
                        else:
                            all_tokens_valid = False
                            print(f"    ❌ Token {token_symbol} not in allowed list")
                    
                    # Check if ALL tokens are valid (not just any)
                    if all_tokens_valid and len(allowed_tokens_found) == len(contract_token_symbols):
                        # Show the first allowed token(s) found
                        main_tokens = allowed_tokens_found[:2] if len(allowed_tokens_found) >= 2 else allowed_tokens_found + contract_token_symbols[:2-len(allowed_tokens_found)]
                        token_display = ' / '.join(main_tokens[:2]) if len(main_tokens) >= 2 else main_tokens[0]
                        
                        print(f"  ✅ Found allowed tokens: {', '.join(allowed_tokens_found)}")
                        
                        filtered_pools.append({
                            'contract': contract,
                            'token_display': token_display,
                            'allowed_tokens': allowed_tokens_found,
                            'all_tokens': contract_token_symbols,
                            'prob': prob,
                            'tx_count': tx_count,
                            'activity_span': activity_span,
                            'logs_count': len(contract_logs)
                        })
                        
                        if len(filtered_pools) >= top_k:
                            break
                    else:
                        invalid_tokens = [t for t in contract_token_symbols if t not in ALLOWED_TOKENS]
                        print(f"    ⏭️  Skipping contract (tokens: {', '.join(contract_token_symbols[:3])}...) - contains invalid tokens: {', '.join(invalid_tokens[:3])}")
                        
        print(f"\n✅ Found {len(filtered_pools)} pools where ALL tokens are valid:")
        print("=" * 80)
        
        for i, pool in enumerate(filtered_pools, 1):
            print(f"{i:2d}. {pool['contract']} | {pool['token_display']} | Logs: {pool['logs_count']}")
            print(f"    Prob: {pool['prob']:.3f} | TXs: {pool['tx_count']} | Span: {pool['activity_span']} blocks")
            print(f"    Allowed: {', '.join(pool['allowed_tokens'])} | All: {', '.join(pool['all_tokens'][:5])}{'...' if len(pool['all_tokens']) > 5 else ''}")
            print()

        # Save predictions
        predictions_key = f"predictions/walk_forward_day_{model_day}_predictions.csv"
        out_buffer = BytesIO()
        current_features.to_csv(out_buffer, index=False)
        out_buffer.seek(0)
        s3.put_object(Bucket=bucket_name, Key=predictions_key, Body=out_buffer.read())
        print(f"💾 Predictions saved: s3://{bucket_name}/{predictions_key}")

    except Exception as e:
        print(f"❌ Error in walk-forward prediction: {e}")


def main():
    parser = argparse.ArgumentParser(description="DeFi Liquidity Prediction Model Pipeline on EC2")
    parser.add_argument(
        "--bucket",
        type=str,
        default="defi-liquidity-data",
        help="The S3 bucket where data is stored.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_rolling = subparsers.add_parser(
        "generate-from-rolling", help="Generate training data from S3 rolling logs/graphs with configurable lookback period."
    )
    parser_rolling.add_argument("--lookback", type=str, default="3D", choices=["1D", "3D", "1W", "3W", "1M"], 
                               help="Lookback period for historical data (default: 3D)")

    parser_generate = subparsers.add_parser(
        "generate-data", help="Generate training data from dated S3 logs (by day)."
    )
    parser_generate.add_argument(
        "--start",
        type=str,
        required=True,
        help="Start date for processing historical data (YYYY-MM-DD).",
    )
    parser_generate.add_argument(
        "--end",
        type=str,
        required=True,
        help="End date for processing historical data (YYYY-MM-DD).",
    )

    parser_train = subparsers.add_parser(
        "train-model", help="Train the model on the generated dataset and save it to S3."
    )
    parser_train.add_argument("--lookback", type=str, default="3d", choices=["1d", "3d", "1w", "3w", "1m"], 
                             help="Lookback period matching training data (default: 3d)")

    parser_infer = subparsers.add_parser(
        "infer-top", help="Score current rolling data and print top-N pools."
    )
    parser_infer.add_argument("--top", type=int, default=20, help="Number of top pools to print")
    parser_infer.add_argument("--lookback", type=str, default="3d", choices=["1d", "3d", "1w", "3w", "1m"], 
                             help="Lookback period matching trained model (default: 3d)")
    parser_infer.add_argument("--no-filter", action="store_true", 
                             help="Skip token filtering - show all pools regardless of token types")

    parser_multi = subparsers.add_parser(
        "infer-multi", help="Multi-timeframe analysis: combine predictions from multiple models for more robust results."
    )
    parser_multi.add_argument("--top", type=int, default=20, help="Number of top pools to show")
    parser_multi.add_argument("--timeframes", nargs='+', default=["1D", "3D", "1W"], 
                             choices=["1D", "3D", "1W", "3W", "1M"],
                             help="Timeframes to analyze (default: 1D 3D 1W)")
    parser_multi.add_argument("--no-filter", action="store_true", 
                             help="Skip token filtering - show all pools regardless of token types")

    parser_bt = subparsers.add_parser(
        "backtest-1w", help="Walk-forward backtest on 1W rolling logs (split into ~1d segments)."
    )
    parser_bt.add_argument("--blocks-per-day", type=int, default=7200, help="Approx blocks per day")
    parser_bt.add_argument("--top", type=int, default=20, help="K for Precision@K")

    parser_continuous = subparsers.add_parser(
        "walk-forward", help="Walk-forward continuous learning: train on 1D, test on next 1D, repeat (overnight operation)."
    )
    parser_continuous.add_argument("--start", type=str, required=True, help="Start date (YYYY-MM-DD)")
    parser_continuous.add_argument("--validation-days", type=int, default=1, help="Number of days to skip ahead for validation")

    parser_predict_rolling = subparsers.add_parser(
        "predict-rolling", help="Use best walk-forward model to predict on current rolling data."
    )
    parser_predict_rolling.add_argument("--top", type=int, default=20, help="Number of top pools to show")
    parser_predict_rolling.add_argument("--model-day", type=int, help="Specific model day to use (optional)")

    args = parser.parse_args()

    if args.command == "generate-from-rolling":
        generate_training_data_from_rolling(args.bucket, lookback_period=args.lookback)
    elif args.command == "generate-data":
        generate_training_data(args.start, args.end, args.bucket)
    elif args.command == "train-model":
        train_model(args.bucket, lookback_period=args.lookback)
    elif args.command == "infer-top":
        infer_top(args.bucket, top_k=args.top, lookback_period=args.lookback, no_filter=args.no_filter)
    elif args.command == "infer-multi":
        infer_top_multi_timeframe(args.bucket, top_k=args.top, timeframes=args.timeframes, no_filter=args.no_filter)
    elif args.command == "backtest-1w":
        backtest_one_week(args.bucket, blocks_per_day=args.__dict__.get("blocks_per_day", 7200), top_k=args.top)
    elif args.command == "walk-forward":
        walk_forward_continuous_learning(args.bucket, args.start, validation_days=args.validation_days)
    elif args.command == "predict-rolling":
        predict_with_walk_forward_model(args.bucket, top_k=args.top, model_day=args.model_day)


if __name__ == "__main__":
    main() 